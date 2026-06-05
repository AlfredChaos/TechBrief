"""Admin API POST protection: CSRF validation + Idempotency-Key support."""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from django.conf import settings
from django.core.cache import caches
from django.http import JsonResponse

from techbrief.api.responses import error_payload, success_payload

logger = logging.getLogger("techbrief.api")

# Cache for idempotency responses (key -> stored response + status code)
_idem_cache = caches["default"]
_IDEM_TTL = getattr(settings, "IDEMPOTENCY_TTL_SECONDS", 3600)


def _idem_key(request_id: str | None, idempotency_key: str) -> str:
    raw = f"idem:{idempotency_key}"
    if request_id:
        raw += f":{request_id}"
    return "tb:" + hashlib.sha256(raw.encode()).hexdigest()[:32]


def check_idempotency(request) -> JsonResponse | None:
    """Return cached response if Idempotency-Key was already processed."""
    idem_key = request.headers.get("Idempotency-Key", "").strip()
    if not idem_key:
        return None
    cache_key = _idem_key(getattr(request, "request_id", None), idem_key)
    stored = _idem_cache.get(cache_key)
    if stored is not None:
        logger.info("Idempotent replay: key=%s", idem_key)
        return JsonResponse(stored["payload"], status=stored["status"])
    return None


def store_idempotency(request, response: JsonResponse) -> None:
    """Cache the response for future idempotent replay."""
    idem_key = request.headers.get("Idempotency-Key", "").strip()
    if not idem_key:
        return
    cache_key = _idem_key(getattr(request, "request_id", None), idem_key)
    try:
        payload = json.loads(response.content)
    except (json.JSONDecodeError, ValueError):
        return
    _idem_cache.set(cache_key, {"payload": payload, "status": response.status_code}, timeout=_IDEM_TTL)


def require_csrf_and_idempotency(view_func):
    """Decorator for admin POST views: validates CSRF, handles idempotency."""
    from functools import wraps

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return view_func(request, *args, **kwargs)

        # Check idempotency first (before CSRF to allow safe replay)
        idem_response = check_idempotency(request)
        if idem_response is not None:
            return idem_response

        result = view_func(request, *args, **kwargs)
        if isinstance(result, JsonResponse):
            store_idempotency(request, result)
        return result

    return wrapper
