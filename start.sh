#!/bin/sh
# start.sh — Cloud Run entrypoint
# Runs migrations on every cold start, then launches gunicorn.
set -e
echo "Running database migrations..."
python manage.py migrate --noinput
echo "Starting gunicorn on port ${PORT:-8080}..."
exec gunicorn Carbomica_app.wsgi:application \
    --bind "0.0.0.0:${PORT:-8080}" \
    --workers 2 \
    --timeout 120 \
    --log-level info
