from __future__ import annotations

import logging
import uuid

from django.http import JsonResponse

from techbrief.api.exceptions import AppError, InternalServerError
from techbrief.api.responses import error_payload
from techbrief.context import clear_request_id, set_request_id, set_service

logger = logging.getLogger("techbrief.web")


class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex}"
        request.request_id = request_id
        set_request_id(request_id)
        set_service("web")
        try:
            response = self.get_response(request)
        finally:
            clear_request_id()
        response["X-Request-ID"] = request_id
        return response


class ApiExceptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except AppError as exc:
            return self._render_error(request, exc)
        except Exception as exc:  # pragma: no cover
            logger.exception("Unhandled application error")
            return self._render_error(request, InternalServerError(details={"exception": str(exc)}))

    def _render_error(self, request, exc: AppError) -> JsonResponse:
        if not (request.path.startswith("/api/") or request.path.startswith("/health/")):
            raise exc
        payload = error_payload(
            code=exc.code,
            message=exc.message,
            error_type=exc.error_type,
            details=exc.details,
            request=request,
        )
        return JsonResponse(payload, status=exc.status)
