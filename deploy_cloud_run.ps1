$ErrorActionPreference = "Stop"
throw "Cloud Run deployment is deferred: shared SQLite is only verified on one host. Complete item 22 storage, identity transport and staging validation first."

# Load .env variables if present
if (Test-Path .env) {
    Get-Content .env | Where-Object { $_ -match "^[^#]*=" } | ForEach-Object {
        $name, $value = $_.Split('=', 2)
        [Environment]::SetEnvironmentVariable($name.Trim(), $value.Trim().Trim('"').Trim("'"), "Process")
    }
}

$PROJECT_ID = if ([string]::IsNullOrEmpty($env:PROJECT_ID)) { "apac-cohort2-track3" } else { $env:PROJECT_ID }
$REGION = if ([string]::IsNullOrEmpty($env:REGION)) { "us-central1" } else { $env:REGION }
$DOCKER_REPO = "us-central1-docker.pkg.dev/$PROJECT_ID/koe-syndicate"

$SERVICES = @("lead-finder", "lead-manager", "sdr", "ui-client")

if ($args.Count -gt 0 -and $args[0] -ne "all") {
    $SERVICES = $args
}

Write-Host "Deploying to Project: $PROJECT_ID | Region: $REGION" -ForegroundColor Cyan

foreach ($SERVICE in $SERVICES) {
    Write-Host "======================================" -ForegroundColor Yellow
    Write-Host "Deploying $SERVICE..." -ForegroundColor Yellow
    Write-Host "======================================" -ForegroundColor Yellow

    $YAML_FILE = "cloudbuild_$($SERVICE.Replace('-', '_')).yaml"

    if (-Not (Test-Path $YAML_FILE)) {
        throw "Build configuration missing: $YAML_FILE; refusing to deploy an unverified image"
    } else {
        Write-Host "Building image for $SERVICE..." -ForegroundColor Cyan
        gcloud builds submit --config="$YAML_FILE" .
        if ($LASTEXITCODE -ne 0) { throw "Build failed for $SERVICE" }
    }

    $IMAGE = "${DOCKER_REPO}/${SERVICE}:latest"

    Write-Host "Deploying $SERVICE to Cloud Run..." -ForegroundColor Cyan
    gcloud run deploy "$SERVICE" `
        --image="$IMAGE" `
        --platform managed `
        --region "$REGION" `
        --project "$PROJECT_ID" `
        --no-allow-unauthenticated `
        --invoker-iam-check `
        --ingress internal `
        --max-instances 1 `
        --update-env-vars="PROJECT_ID=$PROJECT_ID,REGION=$REGION,KOE_MODE=demo,ENABLE_LIVE_CALLS=false,ENABLE_LIVE_EMAIL=false,ENABLE_LIVE_CALENDAR=false"
    if ($LASTEXITCODE -ne 0) { throw "Deployment failed for $SERVICE" }
}

Write-Host "Deployment step finished." -ForegroundColor Green
Write-Host "Make sure to update constants if required!" -ForegroundColor Yellow
