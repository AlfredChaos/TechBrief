from __future__ import annotations

from techbrief.api.responses import success_response


def bootstrap_view(request):
    data = {
        "service": "techbrief",
        "admin_url": "/cms/",
        "django_admin_url": "/django-admin/",
        "health": {
            "live": "/health/live/",
            "ready": "/health/ready/",
        },
    }
    return success_response(
        data=data,
        message="TechBrief bootstrap is running",
        request=request,
    )
