#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT_DIR"

SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-techbrief.settings.test}
REPORT_FILE=${1:-$ROOT_DIR/artifacts/validation/task11_manual_prep_report.json}

uv run python manage.py migrate --settings="$SETTINGS_MODULE" >/dev/null
uv run python manage.py load_site_seed --settings="$SETTINGS_MODULE"
uv run python manage.py validate_acceptance_replays --settings="$SETTINGS_MODULE" --report-file "$REPORT_FILE"

cat <<EOF
Task11.1 manual validation prep completed.

Next steps:
1. Start the site: uv run python manage.py runserver 127.0.0.1:8010 --settings=$SETTINGS_MODULE
2. Open public pages: /, /articles, /about, /privacy, /terms
3. Open admin pages after login: /cms/, /cms/techbrief/
4. Inspect replay report: $REPORT_FILE
5. Follow docs/delivery/Task11-Validation-Guide.md for the exact checklist.
EOF
