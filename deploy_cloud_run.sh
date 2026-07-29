#!/bin/bash
set -e

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
        echo "Warning: $YAML_FILE not found, skipping build."
    else
        echo "Building image for $SERVICE..."
        gcloud builds submit --config="$YAML_FILE" .
    fi
    
    IMAGE="${DOCKER_REPO}/${SERVICE}:latest"
    
    echo "Deploying $SERVICE to Cloud Run..."
    gcloud run deploy "${SERVICE}-service" \
        --image="$IMAGE" \
        --platform managed \
        --region "$REGION" \
        --project "$PROJECT_ID" \
        --allow-unauthenticated \
        --set-env-vars="PROJECT_ID=$PROJECT_ID,REGION=$REGION"
done

echo "Deployment step finished."
echo "Linking services together with updated environment variables..."
./update_deployed_constants.sh
