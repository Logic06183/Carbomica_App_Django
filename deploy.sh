#!/usr/bin/env bash
# deploy.sh — Deploy CARBOMICA to Cloud Run + Firebase Hosting
#
# Usage:
#   ./deploy.sh                  # full deploy (Cloud Run + Firebase Hosting)
#   ./deploy.sh --backend-only   # rebuild and redeploy Cloud Run only
#   ./deploy.sh --hosting-only   # redeploy Firebase Hosting static assets only
#
# Prerequisites:
#   brew install google-cloud-sdk firebase-cli
#   gcloud auth login
#   gcloud auth configure-docker us-central1-docker.pkg.dev
#   firebase login

set -euo pipefail

# ── Config ─────────────────────────────────────────────────────────────────
PROJECT_ID="carbomica-tool"
SERVICE_NAME="carbomica-backend"
REGION="us-central1"
IMAGE="us-central1-docker.pkg.dev/${PROJECT_ID}/${SERVICE_NAME}/app"

# ── Colours ────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${BLUE}▶ $1${NC}"; }
ok()   { echo -e "${GREEN}✔ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠ $1${NC}"; }

# ── Database check ─────────────────────────────────────────────────────────
check_database_url() {
    if [ -z "${DATABASE_URL:-}" ]; then
        warn "DATABASE_URL is not set."
        echo ""
        echo "  CARBOMICA needs a PostgreSQL database. The easiest free option:"
        echo ""
        echo "  1. Go to https://supabase.com → New project (free tier)"
        echo "  2. Project Settings → Database → Connection string → URI"
        echo "     (copy the URI that starts with postgresql://)"
        echo "  3. Export it before running this script:"
        echo ""
        echo "     export DATABASE_URL='postgresql://postgres:PASSWORD@db.XXXX.supabase.co:5432/postgres'"
        echo "     ./deploy.sh"
        echo ""
        exit 1
    fi
    ok "DATABASE_URL is set"
}

# ── Parse args ─────────────────────────────────────────────────────────────
BACKEND=true
HOSTING=true
for arg in "$@"; do
    case $arg in
        --backend-only) HOSTING=false ;;
        --hosting-only) BACKEND=false ;;
    esac
done

# ── Set GCP project ────────────────────────────────────────────────────────
log "Setting active GCP project to ${PROJECT_ID}"
gcloud config set project "${PROJECT_ID}" --quiet

# ── Generate SECRET_KEY if not set ─────────────────────────────────────────
if [ -z "${DJANGO_SECRET_KEY:-}" ]; then
    warn "DJANGO_SECRET_KEY not set — generating one for this deployment"
    export DJANGO_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
fi

# ── Deploy backend to Cloud Run ─────────────────────────────────────────────
if [ "$BACKEND" = true ]; then
    check_database_url

    log "Enabling required GCP APIs (first run only, takes ~60s)"
    gcloud services enable \
        run.googleapis.com \
        cloudbuild.googleapis.com \
        artifactregistry.googleapis.com \
        --quiet 2>/dev/null || true

    log "Creating Artifact Registry repository (first run only)"
    gcloud artifacts repositories create "${SERVICE_NAME}" \
        --repository-format=docker \
        --location="${REGION}" \
        --quiet 2>/dev/null || true

    log "Building and pushing container image via Cloud Build"
    gcloud builds submit \
        --tag "${IMAGE}" \
        --project "${PROJECT_ID}" \
        --quiet

    log "Deploying to Cloud Run"
    gcloud run deploy "${SERVICE_NAME}" \
        --image "${IMAGE}" \
        --platform managed \
        --region "${REGION}" \
        --allow-unauthenticated \
        --port 8080 \
        --memory 512Mi \
        --cpu 1 \
        --min-instances 0 \
        --max-instances 5 \
        --timeout 120 \
        --set-env-vars "DATABASE_URL=${DATABASE_URL}" \
        --set-env-vars "DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}" \
        --set-env-vars "DEBUG=False" \
        --quiet

    CLOUD_RUN_URL=$(gcloud run services describe "${SERVICE_NAME}" \
        --region "${REGION}" \
        --format "value(status.url)")
    ok "Cloud Run deployed → ${CLOUD_RUN_URL}"

    log "Running database migrations on Cloud Run"
    gcloud run jobs create carbomica-migrate \
        --image "${IMAGE}" \
        --region "${REGION}" \
        --set-env-vars "DATABASE_URL=${DATABASE_URL}" \
        --set-env-vars "DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}" \
        --command "python" \
        --args "manage.py,migrate,--noinput" \
        --quiet 2>/dev/null || \
    gcloud run jobs update carbomica-migrate \
        --image "${IMAGE}" \
        --region "${REGION}" \
        --set-env-vars "DATABASE_URL=${DATABASE_URL}" \
        --set-env-vars "DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}" \
        --quiet
    gcloud run jobs execute carbomica-migrate --region "${REGION}" --wait --quiet
    ok "Migrations applied"
fi

# ── Deploy Firebase Hosting ─────────────────────────────────────────────────
if [ "$HOSTING" = true ]; then
    log "Collecting static files for Firebase Hosting"
    python manage.py collectstatic --noinput --clear --quiet

    log "Deploying Firebase Hosting"
    firebase deploy --only hosting --project "${PROJECT_ID}"
    ok "Firebase Hosting deployed → https://${PROJECT_ID}.web.app"
fi

echo ""
ok "🚀 CARBOMICA is live at: https://${PROJECT_ID}.web.app"
echo "   Admin:              https://${PROJECT_ID}.web.app/admin/"
echo "   Firebase console:   https://console.firebase.google.com/project/${PROJECT_ID}"
echo "   Cloud Run console:  https://console.cloud.google.com/run?project=${PROJECT_ID}"
