#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT_DIR"

SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-techbrief.settings.test}
REPORT_FILE=${1:-$ROOT_DIR/artifacts/validation/task11_acceptance_report.json}

uv run python manage.py migrate --settings="$SETTINGS_MODULE" >/dev/null
uv run pytest tests/test_acceptance_validation.py tests/test_content_pipeline_workflow.py tests/test_publishers.py tests/test_public_site.py tests/test_admin_console.py
uv run python manage.py validate_acceptance_replays --settings="$SETTINGS_MODULE" --report-file "$REPORT_FILE"
