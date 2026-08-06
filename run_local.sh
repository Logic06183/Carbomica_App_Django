#!/usr/bin/env bash
# One-command local deployment of the CARBOMICA consortium branch.
set -e
cd "$(dirname "$0")"

python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -q -r requirements.txt

export DEBUG=True
python manage.py migrate
python manage.py seed_consortium
if [ "$1" = "--with-demo-data" ]; then
  python manage.py seed_consortium_demo   # synthetic numbers — never report these
fi

echo ""
echo "──────────────────────────────────────────────────────────"
echo "  CARBOMICA consortium branch — local deployment"
echo "  Sign in with username: craig_parker  password: carbomica-local"
echo "  (or create an admin: python manage.py createsuperuser)"
echo "  Footprint module: http://127.0.0.1:8000/organisation/"
echo "──────────────────────────────────────────────────────────"
echo ""
python manage.py runserver
