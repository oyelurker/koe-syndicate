$ErrorActionPreference = "Stop"

$sourceDir = "C:\Users\savy\Desktop\New folder\Koe Syndicate-main-copy for further"
$targetDir = "C:\Users\savy\Desktop\koe-syndicate"

Write-Host "Creating $targetDir..."
if (Test-Path $targetDir) {
    Remove-Item -Recurse -Force $targetDir
}
New-Item -ItemType Directory -Path $targetDir | Out-Null

Write-Host "Initializing Git..."
Set-Location -Path $targetDir
git init
git config user.name "oyelurker"
git config user.email "oyelurker@github.com"

Write-Host "Copying essential files and directories..."
$itemsToCopy = @(
    "lead_finder",
    "lead_manager",
    "sdr",
    "ui_client",
    "gmail_pubsub_listener",
    "common",
    ".env",
    "requirements.txt",
    "deploy_local.sh",
    "deploy_local.ps1",
    "config.template",
    "__init__.py"
)

foreach ($item in $itemsToCopy) {
    $sourcePath = Join-Path $sourceDir $item
    if (Test-Path $sourcePath) {
        Copy-Item -Path $sourcePath -Destination $targetDir -Recurse -Force
    } else {
        Write-Host "Warning: $sourcePath not found, skipping." -ForegroundColor Yellow
    }
}

Write-Host "Creating virtual environment..."
python -m venv venv

Write-Host "Installing dependencies..."
.\venv\Scripts\pip install -r requirements.txt

Write-Host "Migration Phase 1 complete!" -ForegroundColor Green
