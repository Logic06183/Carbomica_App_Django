#!/usr/bin/env bash
# deploy.sh — Deploy Verdex to Cloud Run + Firebase Hosting
#
# Usage:
#   ./deploy.sh                  # full deploy (Cloud Run + Firebase Hosting)
#   ./deploy.sh --backend-only   # rebuild and redeploy Cloud Run only
#   ./deploy.sh --hosting-only   # redeploy Firebase Hosting static assets only
#
# Preview mode (default — current Verdex deployment):
#   - DEMO_MODE=True bypasses Google OAuth (auto-logs visitors in)
#   - No DATABASE_URL required (ephemeral SQLite in container)
#   - Data resets on every Cloud Run cold start
#
# Production mode (requires DATABASE_URL + Google OAuth env vars):
#   export DATABASE_URL='postgresql://postgres:PWD@HOST:6543/postgres'
#   export GOOGLE_CLIENT_ID='...'
#   export GOOGLE_SECRET='...'
#   PRODUCTION=1 ./deploy.sh
#
# Prerequisites:
#   brew install google-cloud-sdk firebase-cli
#   gcloud auth login
#   firebase login

set -euo pipefail

# ── Config ─────────────────────────────────────────────────────────────────
# GCP project ID — read from active gcloud config, override via env var if needed.
# Run `gcloud config set project <id>` once before first deploy.
PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
if [ -z "${PROJECT_ID}" ]; then
    echo "ERROR: GCP project not configured. Run 'gcloud config set project <id>' or set GCP_PROJECT_ID env var." >&2
    exit 1
fi
SERVICE_NAME="verdex-backend"
HOSTING_SITE="verdex-app"
REGION="us-central1"

# ── Colours ────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${BLUE}▶ $1${NC}"; }
ok()   { echo -e "${GREEN}✔ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠ $1${NC}"; }

# ── Parse args ─────────────────────────────────────────────────────────────
BACKEND=true
HOSTING=true
for arg in "$@"; do
    case $arg in
        --backend-only) HOSTING=false ;;
        --hosting-only) BACKEND=false ;;
    esac
done

# ── Determine env vars based on mode ────────────────────────────────────────
if [ "${PRODUCTION:-0}" = "1" ]; then
    log "Mode: PRODUCTION"
    if [ -z "${DATABASE_URL:-}" ]; then
        warn "PRODUCTION=1 but DATABASE_URL is not set."
        echo "  Set DATABASE_URL to a Supabase Postgres pooler URI (port 6543)."
        exit 1
    fi
    ENV_VARS="BRAND_NAME=Verdex,BRAND_EDITION=verdex,DEMO_MODE=False,DEBUG=False"
    ENV_VARS="${ENV_VARS},DATABASE_URL=${DATABASE_URL}"
    [ -n "${GOOGLE_CLIENT_ID:-}" ] && ENV_VARS="${ENV_VARS},GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}"
    [ -n "${GOOGLE_SECRET:-}" ] && ENV_VARS="${ENV_VARS},GOOGLE_SECRET=${GOOGLE_SECRET}"
else
    log "Mode: PREVIEW (DEMO_MODE bypass auth, ephemeral SQLite)"
    ENV_VARS="BRAND_NAME=Verdex,BRAND_EDITION=verdex,DEMO_MODE=True,DEBUG=False"
fi

# ── Set GCP project ────────────────────────────────────────────────────────
log "Setting active GCP project to ${PROJECT_ID}"
gcloud config set project "${PROJECT_ID}" --quiet

# ── Deploy backend to Cloud Run ─────────────────────────────────────────────
if [ "$BACKEND" = true ]; then
    log "Deploying ${SERVICE_NAME} to Cloud Run from source"
    gcloud run deploy "${SERVICE_NAME}" \
        --source . \
        --region "${REGION}" \
        --project "${PROJECT_ID}" \
        --allow-unauthenticated \
        --set-env-vars "${ENV_VARS}" \
        --quiet

    CLOUD_RUN_URL=$(gcloud run services describe "${SERVICE_NAME}" \
        --region "${REGION}" \
        --format "value(status.url)")
    ok "Cloud Run deployed → ${CLOUD_RUN_URL}"
fi

# ── Deploy Firebase Hosting ─────────────────────────────────────────────────
if [ "$HOSTING" = true ]; then
    log "Collecting static files for Firebase Hosting"
    python manage.py collectstatic --noinput -v 0

    log "Deploying Firebase Hosting site '${HOSTING_SITE}'"
    firebase deploy --only "hosting:${HOSTING_SITE}" --project "${PROJECT_ID}"
    ok "Firebase Hosting deployed → https://${HOSTING_SITE}.web.app"
fi

echo ""
ok "🚀 Verdex is live at: https://${HOSTING_SITE}.web.app"
