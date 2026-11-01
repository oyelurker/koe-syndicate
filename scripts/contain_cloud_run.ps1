param(
    [string]$Project = "apac-cohort2-track3",
    [string]$Region = "us-central1",
    [switch]$IamOnly
)
$ErrorActionPreference = "Stop"
$services = @("lead-finder", "lead-manager", "sdr", "ui-client")
$backup = Join-Path $PSScriptRoot "../.runtime/cloud-containment"
New-Item -ItemType Directory -Path $backup -Force | Out-Null
$results = @()
foreach ($service in $services) {
    $raw = & gcloud run services get-iam-policy $service --project $Project --region $Region --format=json
    if ($LASTEXITCODE -ne 0) { throw "Cannot read IAM for $service" }
    $policy = ($raw -join "`n") | ConvertFrom-Json
    $original = Join-Path $backup "$service-original.json"
    if (-not (Test-Path -LiteralPath $original)) {
        $policy | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $original -Encoding utf8
    }
    $bindings = @()
    foreach ($binding in $policy.bindings) {
        $binding.members = @($binding.members | Where-Object { $_ -notin @("allUsers", "allAuthenticatedUsers") })
        if ($binding.members.Count) { $bindings += $binding }
    }
    $policy | Add-Member -MemberType NoteProperty -Name bindings -Value $bindings -Force
    $restricted = Join-Path $backup "$service-restricted.json"
    $policy | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $restricted -Encoding utf8
    & gcloud run services set-iam-policy $service $restricted --project $Project --region $Region --quiet --format=none
    if ($LASTEXITCODE -ne 0) { throw "Cannot restrict IAM for $service" }
    if (-not $IamOnly) {
        & gcloud run services update $service --project $Project --region $Region --ingress internal --invoker-iam-check --quiet --format=none
        if ($LASTEXITCODE -ne 0) { throw "Cannot restrict ingress for $service; rerun -IamOnly to contain every service when billing blocks updates" }
    }
    $afterRaw = & gcloud run services get-iam-policy $service --project $Project --region $Region --format=json
    if ($LASTEXITCODE -ne 0) { throw "Cannot verify IAM for $service" }
    $after = ($afterRaw -join "`n") | ConvertFrom-Json
    $descriptionRaw = & gcloud run services describe $service --project $Project --region $Region --format=json
    if ($LASTEXITCODE -ne 0) { throw "Cannot verify service for $service" }
    $description = ($descriptionRaw -join "`n") | ConvertFrom-Json
    $public = @($after.bindings | ForEach-Object { $_.members } | Where-Object { $_ -in @("allUsers", "allAuthenticatedUsers") }).Count -gt 0
    $annotations = $description.metadata.annotations
    if ($public -or (-not $IamOnly -and $annotations.'run.googleapis.com/ingress' -ne "internal") -or $annotations.'run.googleapis.com/invoker-iam-disabled' -eq "true") {
        throw "Containment verification failed for $service"
    }
    $results += [pscustomobject]@{service=$service; publicInvoker=$public; ingress=$annotations.'run.googleapis.com/ingress'; invokerIamCheck=$true; revision=$description.status.latestReadyRevisionName; url=$description.status.url}
    Write-Host "Contained and verified: $service"
}
[pscustomobject]@{verifiedAtUtc=[DateTime]::UtcNow.ToString("o"); project=$Project; region=$Region; iamOnly=[bool]$IamOnly; services=$results} |
    ConvertTo-Json -Depth 10 | Set-Content (Join-Path $PSScriptRoot "../docs/p0-cloud-containment.json") -Encoding utf8
