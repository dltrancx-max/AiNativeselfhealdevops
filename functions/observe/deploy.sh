#!/bin/bash

# OBSERVE Pillar Deployment Script
# Deploys the telemetry collection Cloud Function to GCP

set -e

# Configuration
PROJECT_ID="${PROJECT_ID:-}"
REGION="${REGION:-us-central1}"
FUNCTION_NAME="observe-incidents-v1"
MEMORY="1024MB"
TIMEOUT="540s"  # 9 minutes (max for HTTP functions)
MAX_INSTANCES=10

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Configure local PATH for Git Bash so gcloud, bq, and Python are available
configure_local_path() {
    if ! command -v bq &> /dev/null && command -v gcloud &> /dev/null; then
        sdk_root=$(gcloud info --format='value(installation.sdk_root)' 2>/dev/null || true)
        if [ -n "$sdk_root" ]; then
            sdk_bin=$(cygpath -u "$sdk_root/bin" 2>/dev/null || echo "$sdk_root/bin")
            export PATH="$PATH:$sdk_bin"
        fi
    fi

    if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
        if [ -d "/c/Python313" ]; then
            export PATH="$PATH:/c/Python313:/c/Python313/Scripts"
        fi
    fi

    if command -v bq &> /dev/null && ! command -v python3.13 &> /dev/null; then
        local shim_dir="$HOME/bin"
        mkdir -p "$shim_dir"
        if [ ! -x "$shim_dir/python3.13" ]; then
            if [ -f "/c/Python313/python.exe" ]; then
                cat > "$shim_dir/python3.13" <<'PYTHONSHIM'
#!/bin/bash
/c/Python313/python.exe "$@"
PYTHONSHIM
                chmod +x "$shim_dir/python3.13"
            fi
        fi
        export PATH="$shim_dir:$PATH"
    fi

    if [ -f "/c/Python313/python.exe" ]; then
        export CLOUDSDK_PYTHON="/c/Python313/python.exe"
    fi
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    configure_local_path

    # Check if gcloud is installed
    if ! command -v gcloud &> /dev/null; then
        log_error "gcloud CLI is not installed. Please install it first."
        exit 1
    fi

    # Check if authenticated
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n 1 > /dev/null; then
        log_error "Not authenticated with gcloud. Please run 'gcloud auth login' first."
        exit 1
    fi

    # Check if project is set
    if [ -z "$PROJECT_ID" ]; then
        PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
        if [ -z "$PROJECT_ID" ]; then
            log_error "PROJECT_ID not set. Please set it with 'export PROJECT_ID=your-project' or 'gcloud config set project your-project'"
            exit 1
        fi
    fi

    log_info "Using project: $PROJECT_ID"
    log_info "Using region: $REGION"
}

# Enable required APIs
enable_apis() {
    log_info "Enabling required GCP APIs..."

    APIs=(
        "cloudfunctions.googleapis.com"
        "cloudbuild.googleapis.com"
        "run.googleapis.com"
        "logging.googleapis.com"
        "monitoring.googleapis.com"
        "cloudtrace.googleapis.com"
        "bigquery.googleapis.com"
        "pubsub.googleapis.com"
        "eventarc.googleapis.com"
    )

    for api in "${APIs[@]}"; do
        log_info "Enabling $api..."
        gcloud services enable "$api" --project="$PROJECT_ID" --quiet
    done

    log_info "All APIs enabled successfully"
}

# Create BigQuery dataset and table
setup_bigquery() {
    log_info "Setting up BigQuery dataset and table..."

    DATASET_ID="${BIGQUERY_DATASET:-devops_observe}"
    TABLE_ID="${BIGQUERY_TABLE:-incidents}"

    if command -v bq &> /dev/null; then
        if ! bq --project_id="$PROJECT_ID" show --dataset "$DATASET_ID" &>/dev/null 2>&1; then
            log_info "Creating BigQuery dataset: $DATASET_ID"
            bq --project_id="$PROJECT_ID" mk --dataset --location=US "$DATASET_ID"
        else
            log_info "BigQuery dataset $DATASET_ID already exists"
        fi
    else
        log_error "bq CLI is not available. Install the BigQuery component or add it to PATH."
        exit 1
    fi

    log_info "BigQuery setup complete"
}

# Create PubSub topics for Eventarc
setup_pubsub_topics() {
    log_info "Setting up PubSub topics for Eventarc..."

    TOPIC_PREFIX="${TOPIC_PREFIX:-devops-ooda}"
    TOPICS=(
        "${TOPIC_PREFIX}-observe"
        "${TOPIC_PREFIX}-analyze"
        "${TOPIC_PREFIX}-decide"
        "${TOPIC_PREFIX}-act"
        "${TOPIC_PREFIX}-communicate"
    )

    for topic in "${TOPICS[@]}"; do
        if ! gcloud pubsub topics describe "$topic" --project="$PROJECT_ID" &>/dev/null; then
            log_info "Creating PubSub topic: $topic"
            gcloud pubsub topics create "$topic" --project="$PROJECT_ID"
        else
            log_info "PubSub topic $topic already exists"
        fi
    done

    log_info "PubSub topics setup complete"
}

# Deploy Cloud Function
deploy_function() {
    log_info "Deploying Cloud Function..."

    # Disable gen2 functions for this deployment
    gcloud config set functions/gen2 off --quiet

    # Delete existing function if it exists (try both 1st gen and 2nd gen)
    if gcloud functions describe "$FUNCTION_NAME" --project="$PROJECT_ID" --region="$REGION" &>/dev/null; then
        log_info "Deleting existing 1st gen function $FUNCTION_NAME..."
        gcloud functions delete "$FUNCTION_NAME" --project="$PROJECT_ID" --region="$REGION" --quiet
    elif gcloud run services describe "$FUNCTION_NAME" --project="$PROJECT_ID" --region="$REGION" &>/dev/null; then
        log_info "Deleting existing 2nd gen function $FUNCTION_NAME..."
        gcloud run services delete "$FUNCTION_NAME" --project="$PROJECT_ID" --region="$REGION" --quiet
    fi

    # Set environment variables
    ENV_VARS=(
        "GCP_PROJECT=$PROJECT_ID"
        "BIGQUERY_DATASET=${BIGQUERY_DATASET:-devops_observe}"
        "BIGQUERY_TABLE=${BIGQUERY_TABLE:-incidents}"
    )

    ENV_VARS_STR=$(IFS=, ; echo "${ENV_VARS[*]}")

    # Deploy function
    gcloud functions deploy "$FUNCTION_NAME" \
        --project="$PROJECT_ID" \
        --region="$REGION" \
        --runtime=python311 \
        --source=. \
        --entry-point=observe_incidents \
        --trigger-http \
        --allow-unauthenticated \
        --memory="$MEMORY" \
        --timeout="$TIMEOUT" \
        --max-instances="$MAX_INSTANCES" \
        --set-env-vars="$ENV_VARS_STR" \
        --quiet

    if [ $? -eq 0 ]; then
        log_info "Cloud Function deployed successfully!"

        # Get function URL
        FUNCTION_URL=$(gcloud functions describe "$FUNCTION_NAME" \
            --project="$PROJECT_ID" \
            --region="$REGION" \
            --format="value(httpsTrigger.url)")

        log_info "Function URL: $FUNCTION_URL"
        log_info "Health check: $FUNCTION_URL (health endpoint)"
    else
        log_error "Failed to deploy Cloud Function"
        exit 1
    fi
}

# Setup Eventarc triggers
setup_eventarc() {
    log_info "Setting up Eventarc triggers..."

    # Create Eventarc trigger for scheduled execution
    TRIGGER_NAME="observe-scheduled-trigger"

    # Check if trigger already exists
    if gcloud eventarc triggers describe "$TRIGGER_NAME" \
        --project="$PROJECT_ID" \
        --location="$REGION" &>/dev/null; then
        log_info "Eventarc trigger $TRIGGER_NAME already exists"
    else
        log_info "Creating Eventarc trigger for scheduled execution..."

        # This would create a trigger for Cloud Scheduler
        # Note: You may need to create the Cloud Scheduler job separately
        gcloud eventarc triggers create "$TRIGGER_NAME" \
            --project="$PROJECT_ID" \
            --location="$REGION" \
            --destination-run-service="observe-incidents" \
            --destination-run-region="$REGION" \
            --event-filters="type=google.cloud.scheduler.job.v1.executed" \
            --service-account="YOUR_SERVICE_ACCOUNT@YOUR_PROJECT.iam.gserviceaccount.com" || true
    fi

    log_info "Eventarc setup complete"
}

# Create Cloud Scheduler job for periodic execution
setup_scheduler() {
    log_info "Setting up Cloud Scheduler for periodic execution..."

    SCHEDULER_JOB="observe-periodic-collection"
    SCHEDULE="*/5 * * * *"  # Every 5 minutes

    # Check if job already exists
    if gcloud scheduler jobs describe "$SCHEDULER_JOB" \
        --project="$PROJECT_ID" \
        --location="$REGION" &>/dev/null; then
        log_info "Cloud Scheduler job $SCHEDULER_JOB already exists"
    else
        log_info "Creating Cloud Scheduler job..."

        # Get function URL for HTTP trigger
        FUNCTION_URL=$(gcloud functions describe "observe-incidents" \
            --project="$PROJECT_ID" \
            --region="$REGION" \
            --format="value(httpsTrigger.url)")

        if [ -n "$FUNCTION_URL" ]; then
            gcloud scheduler jobs create http "$SCHEDULER_JOB" \
                --project="$PROJECT_ID" \
                --location="$REGION" \
                --schedule="$SCHEDULE" \
                --uri="$FUNCTION_URL" \
                --http-method=POST \
                --headers="Content-Type=application/json" \
                --message-body='{"scheduled": true, "time_window_minutes": 5}' \
                --oidc-service-account-email="YOUR_SERVICE_ACCOUNT@YOUR_PROJECT.iam.gserviceaccount.com" || true
        else
            log_warn "Could not create scheduler job - function URL not found"
        fi
    fi

    log_info "Cloud Scheduler setup complete"
}

# Main deployment function
main() {
    log_info "Starting OBSERVE Pillar deployment..."
    log_info "=================================================="

    check_prerequisites
    enable_apis
    setup_bigquery
    setup_pubsub_topics
    deploy_function
    setup_eventarc
    setup_scheduler

    log_info "=================================================="
    log_info "OBSERVE Pillar deployment completed successfully!"
    log_info ""
    log_info "Next steps:"
    log_info "1. Test the function: curl -X POST YOUR_FUNCTION_URL"
    log_info "2. Check logs: gcloud functions logs read observe-incidents"
    log_info "3. Monitor BigQuery: bq query 'SELECT * FROM devops_observe.incidents LIMIT 10'"
    log_info "4. Proceed to ANALYZE pillar implementation"
}

# Handle command line arguments
case "${1:-}" in
    "check")
        check_prerequisites
        ;;
    "apis")
        enable_apis
        ;;
    "bigquery")
        setup_bigquery
        ;;
    "pubsub")
        setup_pubsub_topics
        ;;
    "deploy")
        deploy_function
        ;;
    "eventarc")
        setup_eventarc
        ;;
    "scheduler")
        setup_scheduler
        ;;
    *)
        main
        ;;
esac