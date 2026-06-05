from __future__ import annotations

from celery import current_app
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.db.utils import OperationalError, ProgrammingError
from django_celery_beat.models import PeriodicTask
from qcloud_cos import CosConfig, CosS3Client


def _ok(name: str, details: dict | None = None) -> dict:
    return {"name": name, "ok": True, "details": details or {}}


def _fail(name: str, reason: str, details: dict | None = None) -> dict:
    payload = {"reason": reason}
    if details:
        payload.update(details)
    return {"name": name, "ok": False, "details": payload}


def check_database() -> dict:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return _ok("database", {"engine": settings.DATABASES["default"]["ENGINE"]})
    except OperationalError as exc:
        return _fail("database", "connection_failed", {"error": str(exc)})


def check_redis() -> dict:
    key = "techbrief:healthcheck"
    try:
        cache.set(key, "ok", timeout=5)
        value = cache.get(key)
        if value != "ok":
            return _fail("redis", "unexpected_cache_value", {"value": value})
        cache.delete(key)
        return _ok("redis", {"location": settings.REDIS_URL})
    except Exception as exc:  # pragma: no cover
        return _fail("redis", "cache_unavailable", {"error": str(exc)})


def check_celery_broker() -> dict:
    try:
        with current_app.connection_for_read() as conn:
            conn.ensure_connection(max_retries=1)
        return _ok("celery", {"broker": settings.CELERY_BROKER_URL})
    except Exception as exc:  # pragma: no cover
        return _fail("celery", "broker_unavailable", {"error": str(exc)})


def check_celery_beat() -> dict:
    try:
        PeriodicTask.objects.count()
        return _ok("celery_beat", {"scheduler": settings.CELERY_BEAT_SCHEDULER})
    except (OperationalError, ProgrammingError) as exc:
        return _fail("celery_beat", "beat_tables_unavailable", {"error": str(exc)})


def check_cos() -> dict:
    config = settings.COS_CONFIG
    if not config["enabled"]:
        return _ok("cos", {"status": "skipped", "enabled": False})
    required_fields = ["secret_id", "secret_key", "bucket", "region"]
    missing = [field for field in required_fields if not config.get(field)]
    if missing:
        return _fail("cos", "missing_configuration", {"missing": missing})
    try:
        client_config = CosConfig(
            Region=config["region"],
            SecretId=config["secret_id"],
            SecretKey=config["secret_key"],
            Token=None,
            Scheme="https",
        )
        CosS3Client(client_config)
        return _ok("cos", {"bucket": config["bucket"], "region": config["region"]})
    except Exception as exc:  # pragma: no cover
        return _fail("cos", "client_init_failed", {"error": str(exc)})


def live_report() -> dict:
    return {
        "status": "ok",
        "checks": [_ok("application", {"app_env": settings.APP_ENV})],
    }


def ready_report() -> dict:
    checks = [
        check_database(),
        check_redis(),
        check_celery_broker(),
        check_celery_beat(),
        check_cos(),
    ]
    all_ok = all(check["ok"] for check in checks)
    return {
        "status": "ok" if all_ok else "degraded",
        "checks": checks,
    }
