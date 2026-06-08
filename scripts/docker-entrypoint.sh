#!/usr/bin/env bash
set -euo pipefail

SERVICE="${TECHBRIEF_SERVICE:-${1:-web}}"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-techbrief.settings.production}"

echo "Starting TechBrief service: ${SERVICE}"

case "${SERVICE}" in
    web)
        exec gunicorn techbrief.wsgi:application \
            --bind 0.0.0.0:8010 \
            --workers "${GUNICORN_WORKERS:-4}" \
            --timeout "${GUNICORN_TIMEOUT:-120}" \
            --access-logfile - \
            --error-logfile -
        ;;
    worker)
        exec celery -A techbrief worker \
            -l info \
            --concurrency "${CELERY_WORKER_CONCURRENCY:-4}" \
            --max-tasks-per-child "${CELERY_MAX_TASKS_PER_CHILD:-100}"
        ;;
    beat)
        exec celery -A techbrief beat \
            -l info \
            --scheduler django_celery_beat.schedulers:DatabaseScheduler
        ;;
    migrate)
        exec python manage.py migrate --noinput
        ;;
    *)
        echo "Unknown service: ${SERVICE}" >&2
        echo "Valid values: web, worker, beat, migrate" >&2
        exit 1
        ;;
esac
