# ============================================================
# Koe Syndicate -- Local Deploy Script (PowerShell / Windows)
# Equivalent of deploy_local.sh for Windows environments.

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Write-Status($msg, $colour = "Cyan") { Write-Host $msg -ForegroundColor $colour }
function Write-Ok($msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "  [FAIL] $msg" -ForegroundColor Red }

Write-Status "======================================================"
Write-Status "     KOE SYNDICATE: SYSTEM ONLINE (Win)   "
Write-Status "======================================================"

# 1. Locate Python inside the venv
$venvPython = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Fail "venv not found. Run: python -m venv venv && .\venv\Scripts\pip install -r requirements.txt"
    exit 1
}
Write-Ok "venv Python: $venvPython"

# 2. Load .env
$envFile = Join-Path $PSScriptRoot ".env"
if (Test-Path $envFile) {
    Write-Status "Loading .env ..."
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#")) {
            $parts = $line -split "=", 2
            if ($parts.Count -eq 2) {
                $k = $parts[0].Trim()
                $v = $parts[1].Trim().Trim('"').Trim("'")
                [System.Environment]::SetEnvironmentVariable($k, $v, "Process")
            }
        }
    }
    Write-Ok ".env loaded"
} else {
    Write-Fail ".env not found. Copy .env.example to .env and fill in your API keys."
    exit 1
}

# 3. Validate mandatory key
$apiKey = [System.Environment]::GetEnvironmentVariable("GOOGLE_API_KEY", "Process")
if (-not $apiKey -or $apiKey -eq "your_google_api_key_here") {
    Write-Fail "GOOGLE_API_KEY is missing or still a placeholder. Edit .env and rerun."
    exit 1
}
Write-Ok "GOOGLE_API_KEY is set"

# Resolve shared paths once before starting any service.
if (-not $env:DB_PATH) { $env:DB_PATH = Join-Path $PSScriptRoot "tokens.db" }
if (-not $env:SECURITY_DB_PATH) { $env:SECURITY_DB_PATH = Join-Path $PSScriptRoot ".runtime/security.db" }
$env:DB_PATH = [System.IO.Path]::GetFullPath($env:DB_PATH)
$env:SECURITY_DB_PATH = [System.IO.Path]::GetFullPath($env:SECURITY_DB_PATH)
& $venvPython -m common.preflight
if ($LASTEXITCODE -ne 0) { throw "Runtime preflight failed; no services were started." }

# 4. Free required ports
# 4. Free required ports
Write-Status "`nChecking ports 3000, 8000, 8081, 8082, 8083, 8084 ..."
foreach ($port in @(3000, 8000, 8081, 8082, 8083, 8084)) {
    $conn = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($conn) {
        $oPid = ($conn.OwningProcess | Select-Object -First 1)
        throw "Port $port is occupied by PID $oPid. Stop the intended existing service before restarting; no process was killed."
    } else {
        Write-Ok "Port $port free"
    }
}

# 5. Collect env vars to forward to jobs
$envVars = @{}
foreach ($k in @("GOOGLE_API_KEY","GOOGLE_MAPS_API_KEY","GOOGLE_CLOUD_PROJECT",
                  "DATASET_ID","TABLE_ID","MODEL","TEMPERATURE","TOP_P","TOP_K","FORCE_SIMPLE_MODE",
                  "GOOGLE_OAUTH_CLIENT_ID","GOOGLE_OAUTH_CLIENT_SECRET","GOOGLE_OAUTH_REDIRECT_URI",
                  "SESSION_SECRET", "ELEVENLABS_API_KEY", "ELEVENLABS_AGENT_ID", "ELEVENLABS_PHONE_NUMBER_ID",
                  "KOE_TOPOLOGY", "KOE_OWNER_EMAIL", "KOE_MODE", "APP_ENV", "TOKEN_ENCRYPTION_KEY",
                  "SERVICE_AUTH_KEYS", "DB_PATH", "SECURITY_DB_PATH", "OUTREACH_ATTACHMENT_DIR",
                  "ENABLE_LIVE_CALLS", "ENABLE_LIVE_EMAIL", "ENABLE_LIVE_CALENDAR", "MAX_CALL_SECONDS",
                  "PHONE_DEFAULT_COUNTRY", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "SALES_EMAIL",
                  "SERVICE_ACCOUNT_FILE", "PROJECT_ID", "SUBSCRIPTION_NAME", "NEXT_PUBLIC_FRONTEND_URL",
                  "UI_CLIENT_SERVICE_URL", "LEAD_FINDER_SERVICE_URL", "LEAD_MANAGER_SERVICE_URL", "SDR_SERVICE_URL")) {
    $envVars[$k] = [System.Environment]::GetEnvironmentVariable($k, "Process")
}

$projectRoot = $PSScriptRoot
$py = $venvPython

# 6. Start background jobs
Write-Status "`nStarting microservices ...`n"

function Start-PySvc {
    param([string]$Name, [string]$Module, [string[]]$ExtraArgs = @())
    $job = Start-Job -Name $Name -ScriptBlock {
        param($py, $module, $extra, $env, $root)
        Set-Location $root
        foreach ($kv in $env.GetEnumerator()) {
            [System.Environment]::SetEnvironmentVariable($kv.Key, $kv.Value, "Process")
        }
        & $py @("-m", $module) @extra 2>&1
    } -ArgumentList $py, $Module, $ExtraArgs, $envVars, $projectRoot
    Write-Ok "$Name started (Job #$($job.Id))"
    return $job
}

$lfJob  = Start-PySvc -Name "LeadFinder"    -Module "lead_finder"
$lmJob  = Start-PySvc -Name "LeadManager"   -Module "lead_manager"   -ExtraArgs @("--port","8082")
$sdrJob = Start-PySvc -Name "SDR"           -Module "sdr"
$gmJob  = Start-PySvc -Name "GmailListener" -Module "gmail_pubsub_listener.gmail_listener_service"
$uiJob  = Start-PySvc -Name "UIClient"      -Module "ui_client"

# Launch NextJS in a separate process to ensure it boots reliably
$nextProcess = Start-Process cmd.exe -WindowStyle Hidden -ArgumentList "/c npm run dev" -WorkingDirectory "$projectRoot\frontend" -PassThru
Write-Ok "NextJS Frontend started (PID $($nextProcess.Id))"

$svcs = @(
    [PSCustomObject]@{ Job=$lfJob;   Name="Lead Finder";           Port=8081 }
    [PSCustomObject]@{ Job=$lmJob;   Name="Lead Manager";          Port=8082 }
    [PSCustomObject]@{ Job=$sdrJob;  Name="SDR";                   Port=8084 }
    [PSCustomObject]@{ Job=$gmJob;   Name="Gmail PubSub Listener"; Port=8083 }
    [PSCustomObject]@{ Job=$uiJob;   Name="UI Client";             Port=8000 }
)

# 7. Monitor 10 second crash window
Write-Status "`nMonitoring startup (10s window) ..."
Start-Sleep -Seconds 10

Write-Status "`n====== Service Health (10s snapshot) ======"
$allOk = $true
foreach ($s in $svcs) {
    $state  = $s.Job.State
    $out    = Receive-Job -Job $s.Job -Keep 2>&1 | Out-String
    if ($state -eq "Failed" -or $out -match "Traceback|Error:|Exception:") {
        Write-Fail "$($s.Name) (port $($s.Port)) - CRASHED"
        ($out -split "`n" | Select-Object -Last 20) | ForEach-Object { Write-Host "    $_" -ForegroundColor Yellow }
        $allOk = $false
    } else {
        Write-Ok "$($s.Name) running on port $($s.Port)  [Job #$($s.Job.Id)]"
    }
}

Write-Status "`n======================================================"
Write-Status "  Lead Finder:        http://127.0.0.1:8081"
Write-Status "  Lead Manager:       http://127.0.0.1:8082"
Write-Status "  SDR:                http://127.0.0.1:8084"
Write-Status "  Gmail Listener:     http://127.0.0.1:8083"
Write-Status "  UI Client (Backend): http://127.0.0.1:8000"
Write-Status "  Next.js Dashboard:   http://localhost:3000"
Write-Status "======================================================"

if ($allOk) { Write-Ok "All services healthy! Next.js Dashboard -> http://localhost:3000" }
else        { Write-Fail "One or more services crashed. Review output above." }

Write-Host "`nUseful commands:" -ForegroundColor Cyan
Write-Host "  View logs:   Receive-Job -Id <id> -Keep" -ForegroundColor DarkCyan
Write-Host "  Stop all:    Get-Job | Stop-Job; Get-Job | Remove-Job" -ForegroundColor DarkCyan
Write-Host "`nPress Ctrl+C to stop all services." -ForegroundColor Magenta

try { Wait-Job -Job ($svcs | ForEach-Object { $_.Job }) }
finally {
    $svcs | ForEach-Object { Stop-Job   -Job $_.Job -ErrorAction SilentlyContinue }
    $svcs | ForEach-Object { Remove-Job -Job $_.Job -ErrorAction SilentlyContinue }
    if ($nextProcess) { Stop-Process -Id $nextProcess.Id -Force -ErrorAction SilentlyContinue }
    Write-Ok "All services stopped."
}
