# 🔧 Environment Variables & Configuration Guide

This document provides comprehensive information about all environment variables and configuration options for the Koe Syndicate platform.

## 📋 Table of Contents

- [Overview](#overview)
- [Global Configuration](#global-configuration)
- [Service-Specific Configuration](#service-specific-configuration)
- [Security Best Practices](#security-best-practices)
- [Configuration Templates](#configuration-templates)
- [Deployment Configurations](#deployment-configurations)

## 🌍 Overview

Koe Syndicate uses a hierarchical configuration system:

1. **Global Configuration** (`.env` in root directory)
2. **Service-Specific Configuration** (`.env` in each service directory)
3. **Environment Variable Overrides** (runtime environment variables)
4. **Default Values** (hardcoded fallbacks in `common/config.py`)

### Configuration Priority
```
Runtime Environment Variables > Service .env > Global .env > Default Values
```

## 🌐 Global Configuration

### Core Configuration File
**Location**: `/.env` (root directory)

```env
# ================================================
# CORE APIs (REQUIRED FOR ALL SERVICES)
# ================================================

# Google API Key for Gemini LLM (REQUIRED)
GOOGLE_API_KEY=your_google_api_key_here

# Google Maps API Key for Places API (REQUIRED)
GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here

# Google Cloud Project ID (REQUIRED)
GOOGLE_CLOUD_PROJECT=your_gcp_project_id_here

# ================================================
# LLM CONFIGURATION
# ================================================

# Primary model for all agents
MODEL=gemini-2.0-flash-lite

# LLM parameters
TEMPERATURE=0.2
TOP_P=0.95
TOP_K=40

# Alternative LLM providers (optional)
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# ================================================
# BIGQUERY CONFIGURATION
# ================================================

# BigQuery dataset and table configuration
DATASET_ID=lead_finder_data
TABLE_ID=business_leads

# ================================================
# ELEVENLABS CONFIGURATION (FOR PHONE CALLS)
# ================================================

# ElevenLabs API key for voice calls
ELEVENLABS_API_KEY=your_elevenlabs_api_key

# ElevenLabs agent ID for conversations
ELEVENLABS_AGENT_ID=your_agent_id

# ElevenLabs phone number ID
ELEVENLABS_PHONE_NUMBER_ID=your_phone_number_id

# ================================================
# EMAIL CONFIGURATION
# ================================================

# SMTP server configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587

# Email credentials
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password_here
FROM_EMAIL=your_email@gmail.com

# Sales email for monitoring
SALES_EMAIL=sales@zemzen.org

# ================================================
# SERVICE AUTHENTICATION
# ================================================

# Google service account key file
GOOGLE_APPLICATION_CREDENTIALS=./koe-syndicate-key.json

# Service account file path (alternative)
SERVICE_ACCOUNT_FILE=.secrets/sales-automation-service.json

# ================================================
# SERVICE URLS (DEFAULT LOCALHOST)
# ================================================

# UI Client
UI_CLIENT_SERVICE_URL=http://localhost:8000

# Agent services
LEAD_FINDER_SERVICE_URL=http://localhost:8081
LEAD_MANAGER_SERVICE_URL=http://localhost:8082
SDR_SERVICE_URL=http://localhost:8084
GMAIL_LISTENER_SERVICE_URL=http://localhost:8083

# ================================================
# OPERATIONAL CONFIGURATION
# ================================================

# Logging level
LOG_LEVEL=INFO

# Environment mode
ENVIRONMENT=development

# Force simple mode (disable complex features)
FORCE_SIMPLE_MODE=false
```

### Environment Variables Reference

| Category | Variable | Description | Required | Default |
|----------|----------|-------------|----------|---------|
| **Core APIs** | `GOOGLE_API_KEY` | Google API key for Gemini LLM | ✅ | None |
| | `GOOGLE_MAPS_API_KEY` | Google Maps Places API key | ✅ | None |
| | `GOOGLE_CLOUD_PROJECT` | GCP project ID | ✅ | None |
| **LLM Config** | `MODEL` | AI model to use | ❌ | gemini-2.0-flash-lite |
| | `TEMPERATURE` | LLM creativity (0.0-2.0) | ❌ | 0.2 |
| | `TOP_P` | Nucleus sampling (0.0-1.0) | ❌ | 0.95 |
| | `TOP_K` | Top-K sampling | ❌ | 40 |
| **Voice Calls** | `ELEVENLABS_API_KEY` | ElevenLabs API key | ❌ | None |
| | `ELEVENLABS_AGENT_ID` | ElevenLabs agent ID | ❌ | None |
| | `ELEVENLABS_PHONE_NUMBER_ID` | Phone number ID | ❌ | None |
| **Email** | `EMAIL_USERNAME` | SMTP username | ❌ | None |
| | `EMAIL_PASSWORD` | SMTP password/app password | ❌ | None |
| | `SALES_EMAIL` | Sales monitoring email | ❌ | sales@zemzen.org |
| **Database** | `DATASET_ID` | BigQuery dataset name | ❌ | lead_finder_data |
| | `TABLE_ID` | BigQuery table name | ❌ | business_leads |
| **Auth** | `GOOGLE_APPLICATION_CREDENTIALS` | Service account key path | ❌ | ./koe-syndicate-key.json |
| **Services** | `UI_CLIENT_SERVICE_URL` | UI Client URL | ❌ | http://localhost:8000 |
| | `LEAD_FINDER_SERVICE_URL` | Lead Finder URL | ❌ | http://localhost:8081 |
| | `LEAD_MANAGER_SERVICE_URL` | Lead Manager URL | ❌ | http://localhost:8082 |
| | `SDR_SERVICE_URL` | SDR Agent URL | ❌ | http://localhost:8084 |

## 🎯 Service-Specific Configuration

### UI Client Configuration
**Location**: `/ui_client/.env`

```env
# UI Client specific settings
UI_CLIENT_PORT=8000
WEBSOCKET_TIMEOUT=300
MAX_WEBSOCKET_CONNECTIONS=100

# Dashboard refresh intervals (seconds)
DASHBOARD_REFRESH_INTERVAL=5
NOTIFICATION_TIMEOUT=10

# UI feature flags
ENABLE_REAL_TIME_UPDATES=true
ENABLE_DARK_MODE=false
SHOW_DEBUG_INFO=false
```

### Lead Finder Configuration
**Location**: `/lead_finder/.env`

```env
# Lead Finder specific settings
LEAD_FINDER_PORT=8081

# Google Maps configuration
MAX_RESULTS_PER_SEARCH=100
SEARCH_RADIUS=25000
DEFAULT_SEARCH_TYPE=restaurant

# Lead filtering
MIN_RATING=3.0
MIN_REVIEW_COUNT=5
EXCLUDE_CHAINS=true

# BigQuery configuration
LEAD_FINDER_DATASET=lead_finder_data
LEAD_FINDER_TABLE=business_leads
ENABLE_BIGQUERY_UPLOAD=true

# Performance settings
ENABLE_RESULT_CACHING=true
CACHE_TTL=3600
```

### Lead Manager Configuration
**Location**: `/lead_manager/.env`

```env
# Lead Manager specific settings
LEAD_MANAGER_PORT=8082

# Email monitoring
SALES_EMAIL=sales@zemzen.org
EMAIL_CHECK_INTERVAL=30

# Calendar configuration
CALENDAR_ID=primary
BUSINESS_HOURS_START=9
BUSINESS_HOURS_END=18
MEETING_DURATION=60
AVAILABILITY_DAYS=7

# Meeting configuration
DEFAULT_MEETING_DURATION=60
MEETING_BUFFER_TIME=15
AUTO_SCHEDULE_MEETINGS=true

# AI analysis settings
MEETING_REQUEST_CONFIDENCE_THRESHOLD=0.7
HOT_LEAD_CONFIDENCE_THRESHOLD=0.8
```

### SDR Agent Configuration
**Location**: `/sdr/.env`

```env
# SDR Agent specific settings
SDR_PORT=8084

# Phone call configuration
ENABLE_PHONE_CALLS=true
MAX_CALL_DURATION=600
CALL_RETRY_ATTEMPTS=3

# Email outreach configuration
ENABLE_EMAIL_OUTREACH=true
EMAIL_DELAY_BETWEEN_SENDS=60
MAX_EMAILS_PER_HOUR=10

# Proposal generation
PROPOSAL_TEMPLATE_PATH=./templates/proposal.html
ENABLE_PDF_GENERATION=true
ATTACH_DEMO_WEBSITES=true

# Research settings
RESEARCH_DEPTH=comprehensive
ENABLE_COMPETITOR_ANALYSIS=true
ENABLE_REVIEW_ANALYSIS=true
```

### Gmail PubSub Listener Configuration
**Location**: `/gmail_pubsub_listener/.env`

```env
# Gmail PubSub specific settings
PROJECT_ID=your_gcp_project_id
SUBSCRIPTION_NAME=gmail-notifications-pull
TOPIC_NAME=gmail-notifications

# Polling configuration (fallback mode)
CRON_INTERVAL=30
ENABLE_CRON_FALLBACK=true

# Message processing
MAX_MESSAGES_PER_PULL=10
MESSAGE_ACK_DEADLINE=60
ENABLE_MESSAGE_BATCHING=false

# Error handling
MAX_RETRY_ATTEMPTS=3
RETRY_DELAY=5
```

## 🔒 Security Best Practices

### API Key Management

```bash
# 1. Use environment variables, never hardcode
export GOOGLE_API_KEY="your-key-here"

# 2. Use separate keys for development/production
export GOOGLE_API_KEY_DEV="dev-key"
export GOOGLE_API_KEY_PROD="prod-key"

# 3. Restrict API key permissions
# - Limit to specific APIs
# - Restrict by IP address
# - Set usage quotas
```

### Service Account Security

```bash
# 1. Use minimal permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:sa@project.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"  # Not admin

# 2. Rotate keys regularly
gcloud iam service-accounts keys create new-key.json \
  --iam-account=sa@project.iam.gserviceaccount.com

# 3. Store keys securely
chmod 600 service-account-key.json
```

### Environment File Security

```bash
# 1. Never commit .env files
echo ".env" >> .gitignore
echo "*.env" >> .gitignore

# 2. Set proper file permissions
chmod 600 .env
chmod 600 */..env

# 3. Use secret management in production
# - Google Secret Manager
# - HashiCorp Vault
# - Kubernetes Secrets
```

### Password and Token Security

```env
# Use app passwords, not account passwords
EMAIL_PASSWORD=app_specific_password

# Use strong, unique passwords
ELEVENLABS_API_KEY=sk_very_long_random_string

# Rotate credentials regularly
GOOGLE_API_KEY=new_rotated_key_monthly
```

## 📝 Configuration Templates

### Development Environment Template

```env
# Development Configuration
ENVIRONMENT=development
LOG_LEVEL=DEBUG

# Use local services
UI_CLIENT_SERVICE_URL=http://localhost:8000
LEAD_FINDER_SERVICE_URL=http://localhost:8081
LEAD_MANAGER_SERVICE_URL=http://localhost:8082
SDR_SERVICE_URL=http://localhost:8084

# Development API keys (restricted)
GOOGLE_API_KEY=dev_google_api_key
GOOGLE_MAPS_API_KEY=dev_maps_api_key

# Mock/sandbox configurations
ELEVENLABS_API_KEY=test_elevenlabs_key
FORCE_SIMPLE_MODE=true

# Development database
GOOGLE_CLOUD_PROJECT=koe-syndicate-dev
DATASET_ID=dev_lead_data
```

### Staging Environment Template

```env
# Staging Configuration
ENVIRONMENT=staging
LOG_LEVEL=INFO

# Staging service URLs
UI_CLIENT_SERVICE_URL=https://ui-staging.koe-syndicate.com
LEAD_FINDER_SERVICE_URL=https://lead-finder-staging.koe-syndicate.com
LEAD_MANAGER_SERVICE_URL=https://lead-manager-staging.koe-syndicate.com
SDR_SERVICE_URL=https://sdr-staging.koe-syndicate.com

# Staging API keys
GOOGLE_API_KEY=staging_google_api_key
GOOGLE_MAPS_API_KEY=staging_maps_api_key
ELEVENLABS_API_KEY=staging_elevenlabs_key

# Staging database
GOOGLE_CLOUD_PROJECT=koe-syndicate-staging
DATASET_ID=staging_lead_data

# Reduced quotas for staging
MAX_RESULTS_PER_SEARCH=50
MAX_EMAILS_PER_HOUR=5
```

### Production Environment Template

```env
# Production Configuration
ENVIRONMENT=production
LOG_LEVEL=WARNING

# Production service URLs
UI_CLIENT_SERVICE_URL=https://app.koe-syndicate.com
LEAD_FINDER_SERVICE_URL=https://lead-finder.koe-syndicate.com
LEAD_MANAGER_SERVICE_URL=https://lead-manager.koe-syndicate.com
SDR_SERVICE_URL=https://sdr.koe-syndicate.com

# Production API keys (use secret management)
GOOGLE_API_KEY=${GOOGLE_API_KEY_SECRET}
GOOGLE_MAPS_API_KEY=${GOOGLE_MAPS_API_KEY_SECRET}
ELEVENLABS_API_KEY=${ELEVENLABS_API_KEY_SECRET}

# Production database
GOOGLE_CLOUD_PROJECT=koe-syndicate-prod
DATASET_ID=production_lead_data

# Production optimizations
ENABLE_RESULT_CACHING=true
CACHE_TTL=7200
MAX_WEBSOCKET_CONNECTIONS=1000
```

## 🚀 Deployment Configurations

### Docker Environment Variables

```bash
# Docker run with environment file
docker run --env-file .env koe-syndicate-ui-client

# Docker run with individual variables
docker run \
  -e GOOGLE_API_KEY="your-key" \
  -e GOOGLE_CLOUD_PROJECT="your-project" \
  koe-syndicate-ui-client

# Docker Compose with environment
# docker-compose.yml
services:
  ui-client:
    image: koe-syndicate-ui-client
    environment:
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT}
    env_file:
      - .env
```

### Google Cloud Run Configuration

```bash
# Deploy with environment variables
gcloud run deploy ui-client-service \
  --source . \
  --set-env-vars="GOOGLE_API_KEY=${GOOGLE_API_KEY}" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT}"

# Use Cloud Run env file
gcloud run services replace service.yaml
```

**service.yaml example**:
```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: ui-client-service
spec:
  template:
    spec:
      containers:
      - image: gcr.io/project/ui-client
        env:
        - name: GOOGLE_API_KEY
          valueFrom:
            secretKeyRef:
              key: google-api-key
              name: koe-syndicate-secrets
        - name: GOOGLE_CLOUD_PROJECT
          value: "koe-syndicate-prod"
```

### Kubernetes Configuration

```yaml
# ConfigMap for non-sensitive config
apiVersion: v1
kind: ConfigMap
metadata:
  name: koe-syndicate-config
data:
  GOOGLE_CLOUD_PROJECT: "koe-syndicate-prod"
  DATASET_ID: "production_lead_data"
  LOG_LEVEL: "INFO"

---
# Secret for sensitive data
apiVersion: v1
kind: Secret
metadata:
  name: koe-syndicate-secrets
type: Opaque
data:
  GOOGLE_API_KEY: base64_encoded_key
  ELEVENLABS_API_KEY: base64_encoded_key

---
# Deployment using ConfigMap and Secret
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ui-client
spec:
  template:
    spec:
      containers:
      - name: ui-client
        image: koe-syndicate-ui-client
        envFrom:
        - configMapRef:
            name: koe-syndicate-config
        - secretRef:
            name: koe-syndicate-secrets
```

## 🔍 Configuration Validation

### Environment Variable Checker Script

```bash
#!/bin/bash
# check_env.sh - Validate environment configuration

echo "🔍 Checking Koe Syndicate configuration..."

# Required variables
REQUIRED_VARS=(
  "GOOGLE_API_KEY"
  "GOOGLE_MAPS_API_KEY"
  "GOOGLE_CLOUD_PROJECT"
)

# Check required variables
for var in "${REQUIRED_VARS[@]}"; do
  if [ -z "${!var}" ]; then
    echo "❌ Missing required variable: $var"
    exit 1
  else
    echo "✅ $var is set"
  fi
done

# Test API connectivity
echo "🌐 Testing API connectivity..."

# Test Google API
if curl -s "https://generativelanguage.googleapis.com/v1beta/models?key=$GOOGLE_API_KEY" > /dev/null; then
  echo "✅ Google API accessible"
else
  echo "❌ Google API connection failed"
fi

# Test Google Maps API
if curl -s "https://maps.googleapis.com/maps/api/place/findplacefromtext/json?input=test&inputtype=textquery&key=$GOOGLE_MAPS_API_KEY" > /dev/null; then
  echo "✅ Google Maps API accessible"
else
  echo "❌ Google Maps API connection failed"
fi

echo "✅ Configuration check complete"
```

### Python Configuration Validator

```python
#!/usr/bin/env python3
# validate_config.py - Validate configuration

import os
import sys
from google.cloud import bigquery
from google.oauth2 import service_account

def validate_config():
    """Validate Koe Syndicate configuration"""
    
    # Check required environment variables
    required_vars = [
        'GOOGLE_API_KEY',
        'GOOGLE_MAPS_API_KEY', 
        'GOOGLE_CLOUD_PROJECT'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing required variables: {', '.join(missing_vars)}")
        return False
    
    # Test BigQuery access
    try:
        client = bigquery.Client()
        datasets = list(client.list_datasets(max_results=1))
        print("✅ BigQuery access successful")
    except Exception as e:
        print(f"❌ BigQuery access failed: {e}")
        return False
    
    # Test service account
    sa_file = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if sa_file and os.path.exists(sa_file):
        try:
            creds = service_account.Credentials.from_service_account_file(sa_file)
            print("✅ Service account key valid")
        except Exception as e:
            print(f"❌ Service account key invalid: {e}")
            return False
    
    print("✅ All configuration checks passed")
    return True

if __name__ == "__main__":
    if not validate_config():
        sys.exit(1)
```

## 📚 Configuration Troubleshooting

### Common Issues

1. **API Key Not Working**:
```bash
# Check key format and restrictions
curl "https://generativelanguage.googleapis.com/v1beta/models?key=$GOOGLE_API_KEY"
```

2. **Service Account Issues**:
```bash
# Check file permissions
ls -la $GOOGLE_APPLICATION_CREDENTIALS
chmod 600 $GOOGLE_APPLICATION_CREDENTIALS
```

3. **BigQuery Access Denied**:
```bash
# Check project and permissions
gcloud auth list
gcloud config get-value project
```

4. **Service URL Connectivity**:
```bash
# Test service connectivity
curl -f http://localhost:8000/health
```

### Debug Mode Configuration

```env
# Enable debug mode for troubleshooting
LOG_LEVEL=DEBUG
SHOW_DEBUG_INFO=true
ENABLE_VERBOSE_LOGGING=true

# Test configurations
FORCE_SIMPLE_MODE=true
USE_MOCK_DATA=true
SKIP_EXTERNAL_APIS=true
```

---

For more information about specific service configurations, see the individual service README files in their respective directories.

**Need help?** Check the [Installation Guide](INSTALLATION.md) or open an issue on GitHub.