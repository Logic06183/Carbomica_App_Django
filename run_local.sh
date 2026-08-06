#!/usr/bin/env bash
# One-command local deployment of the CARBOMICA consortium branch.
set -e
cd "$(dirname "$0")"

python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -q -r requirements.txt

export DEBUG=True
python manage.py migrate
python manage.py seed_consortium_demo

echo ""
echo "──────────────────────────────────────────────────────────"
echo "  CARBOMICA consortium branch — local deployment"
echo "  Sign in with username: demo_consortium  password: carbomica-demo"
echo "  (or create an admin: python manage.py createsuperuser)"
echo "  Footprint module: http://127.0.0.1:8000/organisation/"
echo "──────────────────────────────────────────────────────────"
echo ""
python manage.py runserver
