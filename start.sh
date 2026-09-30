#!/bin/sh
# start.sh — Cloud Run entrypoint
# Runs migrations + idempotent data syncs on every cold start, then launches gunicorn.
set -e
echo "Running database migrations..."
python manage.py migrate --noinput
echo "Syncing intervention library (idempotent)..."
python manage.py sync_interventions
# Seed demo facilities. The preview deployment uses an in-image SQLite database,
# which Cloud Run restores to its pristine state on every cold start — without
# this the app boots to an empty state mid-demo. Runs after sync_interventions
# so newly seeded facilities are curated against sector-tagged interventions,
# and before backfill so they get their intervention rows. Idempotent, and
# skipped when SEED_DEMO_DATA=False (set this for any real production database).
if [ "${SEED_DEMO_DATA:-True}" = "True" ]; then
    echo "Seeding demo data (idempotent)..."
    python manage.py seed_demo_data
fi
echo "Backfilling facility interventions (idempotent)..."
python manage.py backfill_facility_interventions
echo "Starting gunicorn on port ${PORT:-8080}..."
exec gunicorn Carbomica_app.wsgi:application \
    --bind "0.0.0.0:${PORT:-8080}" \
    --workers 2 \
    --timeout 120 \
    --log-level info
