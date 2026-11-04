#!/bin/bash
set -e
echo "Cloud Run deployment is deferred: shared SQLite requires one host. Complete item 22 storage, identity transport and staging validation first." >&2
exit 1

# Load environment variables if present
if [ -f .env ]; then
  set -o allexport
  source .env
  set +o allexport
fi

# Default project variables
PROJECT_ID="${PROJECT_ID:-apac-cohort2-track3}"
REGION="${REGION:-us-central1}"
DOCKER_REPO="us-central1-docker.pkg.dev/${PROJECT_ID}/koe-syndicate"

# Default services to deploy if none specified
SERVICES=("lead-finder" "lead-manager" "sdr" "ui-client")

if [ $# -gt 0 ] && [ "$1" != "all" ]; then
    SERVICES=("$@")
fi

echo "Deploying to Project: $PROJECT_ID | Region: $REGION"

for SERVICE in "${SERVICES[@]}"; do
    echo "======================================"
    echo "Deploying $SERVICE..."
    echo "======================================"

    # Map service name to yaml file
    YAML_FILE="cloudbuild_${SERVICE/-/_}.yaml"

    if [ ! -f "$YAML_FILE" ]; then
        echo "Build configuration missing: $YAML_FILE; refusing to deploy an unverified image." >&2
        exit 1
    else
        echo "Building image for $SERVICE..."
        gcloud builds submit --config="$YAML_FILE" .
    fi

    IMAGE="${DOCKER_REPO}/${SERVICE}:latest"

    echo "Deploying $SERVICE to Cloud Run..."
    gcloud run deploy "$SERVICE" \
        --image="$IMAGE" \
        --platform managed \
        --region "$REGION" \
        --project "$PROJECT_ID" \
        --no-allow-unauthenticated \
        --invoker-iam-check \
        --ingress internal \
        --max-instances 1 \
        --update-env-vars="PROJECT_ID=$PROJECT_ID,REGION=$REGION,KOE_MODE=demo,ENABLE_LIVE_CALLS=false,ENABLE_LIVE_EMAIL=false,ENABLE_LIVE_CALENDAR=false"
done

echo "Deployment step finished."
echo "Configure authenticated service URLs and persistent storage before any live rollout; see docs/P0-SECURITY.md."
