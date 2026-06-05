from __future__ import annotations

from django.views.decorators.http import require_GET

from techbrief.api.responses import success_response
from techbrief.health.checks import live_report, ready_report


@require_GET
def live_view(request):
    report = live_report()
    return success_response(data=report, message="service is alive", request=request)


@require_GET
def ready_view(request):
    report = ready_report()
    status = 200 if report["status"] == "ok" else 503
    return success_response(
        data=report,
        message="service is ready" if status == 200 else "service is not ready",
        status=status,
        request=request,
    )
