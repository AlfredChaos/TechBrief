from __future__ import annotations

from django.http import JsonResponse

from techbrief.context import get_request_id, get_run_id


def build_meta(request=None, extra: dict | None = None) -> dict:
    meta = {
        "request_id": getattr(request, "request_id", None) or get_request_id(),
    }
    run_id = get_run_id()
    if run_id:
        meta["run_id"] = run_id
    if extra:
        meta.update(extra)
    return meta


def success_payload(data=None, message: str = "success", code: str = "OK", request=None) -> dict:
    return {
        "success": True,
        "code": code,
        "message": message,
        "data": data,
        "meta": build_meta(request=request),
    }


def error_payload(*, code: str, message: str, error_type: str, details: dict | None = None, request=None) -> dict:
    return {
        "success": False,
        "code": code,
        "message": message,
        "data": None,
        "error": {
            "type": error_type,
            "details": details or {},
        },
        "meta": build_meta(request=request),
    }


def success_response(data=None, message: str = "success", code: str = "OK", status: int = 200, request=None) -> JsonResponse:
    return JsonResponse(success_payload(data=data, message=message, code=code, request=request), status=status)
