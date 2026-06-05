from __future__ import annotations

import json
import logging

from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_http_methods

from techbrief.api.responses import error_payload, success_response
from techbrief.apps.web.models import ListingPageCode, StaticPageCode
from techbrief.apps.web.public_site import (
    LOCALE_COOKIE_NAME,
    build_detail_context,
    build_home_context,
    build_static_context,
    build_unsubscribe_context,
    create_subscription,
    get_detail_snapshot,
    get_listing_page,
    get_static_page,
    get_content_index_context,
    normalize_locale,
    serialize_detail_payload,
    serialize_listing_payload,
    unsubscribe_subscription,
)

logger = logging.getLogger(__name__)

# 1x1 transparent GIF (43 bytes)
_TRACKING_PIXEL = (
    b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00"
    b"\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21"
    b"\xf9\x04\x00\x00\x00\x00\x00\x2c\x00\x00"
    b"\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44"
    b"\x01\x00\x3b"
)


def _apply_locale_cookie(request, response):
    locale = request.GET.get("locale")
    normalized = normalize_locale(locale) if locale else None
    if normalized and locale:
        response.set_cookie(
            LOCALE_COOKIE_NAME,
            normalized,
            max_age=60 * 60 * 24 * 30,
            samesite="Lax",
        )
    return response


@require_GET
def home_view(request):
    response = render(request, "web/home_page.html", build_home_context(request))
    return _apply_locale_cookie(request, response)


@require_GET
def articles_view(request):
    page = get_listing_page(ListingPageCode.ARTICLES)
    response = render(request, "web/listing_page.html", get_content_index_context(request, page))
    return _apply_locale_cookie(request, response)


@require_GET
def archive_view(request):
    page = get_listing_page(ListingPageCode.ARCHIVE)
    response = render(
        request,
        "web/listing_page.html",
        get_content_index_context(request, page, archive_mode=True),
    )
    return _apply_locale_cookie(request, response)


@require_GET
def article_detail_view(request, slug: str):
    snapshot = get_detail_snapshot(slug, content_type="article")
    response = render(request, "web/detail_page.html", build_detail_context(request, snapshot))
    return _apply_locale_cookie(request, response)


@require_GET
def video_detail_view(request, slug: str):
    snapshot = get_detail_snapshot(slug, content_type="video")
    response = render(request, "web/detail_page.html", build_detail_context(request, snapshot))
    return _apply_locale_cookie(request, response)


@require_GET
def static_page_view(request, page_code: str):
    code_map = {
        "about": StaticPageCode.ABOUT,
        "privacy": StaticPageCode.PRIVACY,
        "terms": StaticPageCode.TERMS,
    }
    try:
        code = code_map[page_code]
    except KeyError as exc:
        raise Http404("static page not found") from exc
    response = render(request, "web/static_page.html", build_static_context(request, get_static_page(code)))
    return _apply_locale_cookie(request, response)


@require_GET
def unsubscribe_page_view(request, token: str):
    response = render(request, "web/unsubscribe_page.html", build_unsubscribe_context(request, token))
    return _apply_locale_cookie(request, response)


@require_GET
def public_content_items_api(request):
    return success_response(data=serialize_listing_payload(request), request=request)


@require_GET
def public_content_item_detail_api(request, slug: str):
    return success_response(data=serialize_detail_payload(request, slug), request=request)


@require_http_methods(["POST"])
def create_subscription_api(request):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse(
            error_payload(
                code="SYSTEM_VALIDATION_ERROR",
                message="invalid json body",
                error_type="ValidationError",
                details={},
                request=request,
            ),
            status=400,
        )

    try:
        response_payload, status = create_subscription(request=request, payload=payload)
    except KeyError:
        return JsonResponse(
            error_payload(
                code="IDEMPOTENCY_KEY_REQUIRED",
                message="idempotency key is required",
                error_type="ValidationError",
                details={"header": "Idempotency-Key"},
                request=request,
            ),
            status=400,
        )
    except ValueError as exc:
        return JsonResponse(
            error_payload(
                code="SYSTEM_VALIDATION_ERROR",
                message=str(exc) or "validation failed",
                error_type="ValidationError",
                details={},
                request=request,
            ),
            status=400,
        )

    return JsonResponse(response_payload, status=status)


@require_GET
def tracking_pixel_view(request):
    """Return a 1x1 transparent GIF for email open tracking."""
    subscriber_id = request.GET.get("sid", "")
    content_id = request.GET.get("cid", "")
    logger.info(
        "tracking_pixel sid=%s cid=%s ua=%s",
        subscriber_id,
        content_id,
        request.headers.get("User-Agent", ""),
    )
    return HttpResponse(
        _TRACKING_PIXEL,
        content_type="image/gif",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@require_http_methods(["POST"])
def unsubscribe_subscription_api(request):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse(
            error_payload(
                code="SYSTEM_VALIDATION_ERROR",
                message="invalid json body",
                error_type="ValidationError",
                details={},
                request=request,
            ),
            status=400,
        )

    token = payload.get("token")
    if not token:
        return JsonResponse(
            error_payload(
                code="SYSTEM_VALIDATION_ERROR",
                message="token is required",
                error_type="ValidationError",
                details={"field": "token"},
                request=request,
            ),
            status=400,
        )

    try:
        response_payload, status = unsubscribe_subscription(request=request, token=token)
    except Http404:
        return JsonResponse(
            error_payload(
                code="SUBSCRIBER_NOT_FOUND",
                message="subscriber not found",
                error_type="NotFoundError",
                details={"token": token},
                request=request,
            ),
            status=404,
        )

    return JsonResponse(response_payload, status=status)
