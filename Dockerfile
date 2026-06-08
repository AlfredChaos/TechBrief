# ============================================================
# TechBrief — multi-stage Docker build
# ============================================================
# TECHBRIEF_SERVICE env var controls the entrypoint:
#   web    → gunicorn (Django web server)
#   worker → celery worker
#   beat   → celery beat scheduler
# ============================================================

# ---------- build stage ----------
FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv

WORKDIR /build
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# ---------- runtime stage ----------
FROM python:3.12-slim

# Security: non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /build/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy application code
COPY . .

# Collect static files (WhiteNoise serves them)
RUN DJANGO_SETTINGS_MODULE=techbrief.settings.production \
    SECRET_KEY=build-time-secret \
    DATABASE_URL=sqlite:///devnull \
    python manage.py collectstatic --noinput 2>/dev/null || true

# Entrypoint script
COPY scripts/docker-entrypoint.sh /app/scripts/docker-entrypoint.sh
RUN chmod +x /app/scripts/docker-entrypoint.sh

USER appuser

EXPOSE 8010

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
CMD ["web"]
