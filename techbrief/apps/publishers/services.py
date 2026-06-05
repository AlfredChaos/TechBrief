from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date
from typing import Any

from django.conf import settings
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.http import Http404
from django.template.defaultfilters import striptags
from django.utils import timezone
from django.utils.text import slugify

from techbrief.api.responses import success_payload
from techbrief.apps.content_pipeline.models import (
    ContentItem,
    ContentStage,
    ContentStatus,
    ContentType,
    TriggeredBy,
)
from techbrief.apps.core.models import IdempotencyKey, IdempotencyKeyStatus, User
from techbrief.apps.integrations.adapters import (
    BaseEmailAdapter,
    BaseWeChatDraftAdapter,
    EmailMessage,
    IntegrationError,
    MockEmailAdapter,
    MockWeChatDraftAdapter,
    WeChatDraftPayload,
    get_email_adapter,
    get_wechat_draft_adapter,
)
from techbrief.apps.observability.models import RunLog, RunLogStatus
from techbrief.apps.publishers.models import (
    ContentPageSnapshot,
    EmailDelivery,
    EmailDeliveryStatus,
    EmailDigestBatch,
    EmailDigestBatchItem,
    EmailDigestStatus,
    PageKind,
    PublishChannel,
    PublishRecord,
    PublishStatus,
    Subscriber,
    SubscriberSourcePage,
    SubscriberStatus,
    WeChatDraftDetail,
    WeChatSourceMode,
)

SUBSCRIPTION_ACTION = "create_subscription"


def _hash_request_body(data: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()


def subscribe_email(*, request, payload: dict[str, Any]) -> tuple[dict, int]:
    email = (payload.get("email") or "").strip().lower()
    source_page = payload.get("source_page") or SubscriberSourcePage.UNKNOWN
    locale = payload.get("locale") or "zh-CN"
    idempotency_key = request.headers.get("Idempotency-Key")

    validate_email(email)
    if source_page not in SubscriberSourcePage.values:
        raise ValueError("invalid source_page")
    if not idempotency_key:
        raise KeyError("missing idempotency key")

    scope = f"public:{email}"
    request_hash = _hash_request_body({"email": email, "source_page": source_page, "locale": locale})
    existing_key = IdempotencyKey.objects.filter(
        key=idempotency_key,
        operator_scope=scope,
        action=SUBSCRIPTION_ACTION,
    ).first()
    if existing_key and existing_key.status == IdempotencyKeyStatus.SUCCEEDED and existing_key.response_payload:
        return existing_key.response_payload, existing_key.response_status or 200

    with transaction.atomic():
        try:
            idem_key, _ = IdempotencyKey.objects.get_or_create(
                key=idempotency_key,
                operator_scope=scope,
                action=SUBSCRIPTION_ACTION,
                defaults={
                    "request_method": "POST",
                    "request_path": request.path,
                    "request_hash": request_hash,
                    "request_id": getattr(request, "request_id", ""),
                },
            )
        except IntegrityError:
            idem_key = IdempotencyKey.objects.get(
                key=idempotency_key,
                operator_scope=scope,
                action=SUBSCRIPTION_ACTION,
            )

        if idem_key.status == IdempotencyKeyStatus.SUCCEEDED and idem_key.response_payload:
            return idem_key.response_payload, idem_key.response_status or 200

        subscriber, _ = Subscriber.objects.get_or_create(
            email=email,
            defaults={
                "source_page": source_page,
                "locale": locale,
                "unsubscribe_token": uuid.uuid4().hex,
                "status": SubscriberStatus.ACTIVE,
            },
        )
        if subscriber.status != SubscriberStatus.ACTIVE:
            subscriber.status = SubscriberStatus.ACTIVE
            subscriber.unsubscribed_at = None
        subscriber.source_page = source_page
        subscriber.locale = locale
        subscriber.save()

        response_data = {
            "subscriber_id": str(subscriber.id),
            "status": subscriber.status,
            "subscribed_at": serialize_datetime(subscriber.subscribed_at),
            "unsubscribe_token": subscriber.unsubscribe_token,
        }
        response_payload = success_payload(data=response_data, message="subscribed", request=request)
        idem_key.status = IdempotencyKeyStatus.SUCCEEDED
        idem_key.response_code = "OK"
        idem_key.response_status = 200
        idem_key.response_payload = response_payload
        idem_key.request_hash = request_hash
        idem_key.request_id = getattr(request, "request_id", "")
        idem_key.save()
        return response_payload, 200


def unsubscribe_by_token(*, request, token: str) -> tuple[dict, int]:
    subscriber = Subscriber.objects.filter(unsubscribe_token=token).first()
    if subscriber is None:
        raise Http404("subscriber not found")

    with transaction.atomic():
        if subscriber.status != SubscriberStatus.UNSUBSCRIBED:
            subscriber.status = SubscriberStatus.UNSUBSCRIBED
            subscriber.unsubscribed_at = timezone.now()
            subscriber.save()

    payload = success_payload(
        data={
            "status": subscriber.status,
            "unsubscribed_at": serialize_datetime(subscriber.unsubscribed_at),
        },
        message="unsubscribed",
        request=request,
    )
    return payload, 200


def publish_content_item(
    content_item: ContentItem,
    *,
    run_id: uuid.UUID | None = None,
    request_id: str | None = None,
    triggered_by: str = TriggeredBy.SYSTEM,
    triggered_by_user: User | None = None,
) -> dict[str, Any]:
    run_id = run_id or uuid.uuid4()
    log = _create_run_log(
        content_item=content_item,
        stage=ContentStage.PUBLISH,
        run_id=run_id,
        request_id=request_id,
        triggered_by=triggered_by,
        triggered_by_user=triggered_by_user,
        retryable=True,
    )
    now = timezone.now()

    try:
        with transaction.atomic():
            slug = _ensure_content_slug(content_item)
            snapshot, _ = ContentPageSnapshot.objects.update_or_create(
                content_item=content_item,
                defaults={
                    "page_kind": _resolve_page_kind(content_item),
                    "slug": slug,
                    "source_name_snapshot": content_item.source_name_snapshot,
                    "title_original_snapshot": content_item.title_original,
                    "title_zh_snapshot": content_item.title_zh or content_item.title_original,
                    "summary_zh_snapshot": content_item.summary_zh or content_item.summary_original,
                    "body_original_md_snapshot": content_item.content_md or "",
                    "body_zh_md_snapshot": content_item.zh_md or content_item.content_md or content_item.title_original,
                    "author_or_speaker_snapshot": content_item.author_or_speaker,
                    "source_url_snapshot": content_item.source_url or content_item.canonical_url or settings.PUBLIC_BASE_URL,
                    "canonical_url_snapshot": content_item.canonical_url or content_item.source_url,
                    "published_at_source_snapshot": content_item.published_at_source,
                    "supports_bilingual": bool(content_item.supports_bilingual and content_item.content_md),
                    "disclaimer_md_snapshot": _build_disclaimer_md(content_item),
                    "seo_title": content_item.title_zh or content_item.title_original,
                    "seo_description": content_item.summary_zh or content_item.summary_original,
                    "is_published": True,
                    "published_at": now,
                    "last_synced_at": now,
                },
            )
            record = PublishRecord.objects.create(
                content_item=content_item,
                channel=PublishChannel.WEB,
                status=PublishStatus.SUCCESS,
                request_id=request_id,
                run_id=run_id,
                triggered_by=triggered_by,
                triggered_by_user=triggered_by_user,
                external_id=slug,
                payload_snapshot={"slug": slug},
                response_snapshot={"snapshot_id": str(snapshot.id), "is_published": True},
                published_at=now,
            )
            content_item.web_slug = slug
            content_item.status = ContentStatus.PUBLISHED
            content_item.current_stage = ContentStage.NOTIFY
            content_item.published_at_web = now
            content_item.last_processed_at = now
            content_item.latest_run_id = run_id
            content_item.last_error_code = None
            content_item.last_error_message = None
            content_item.last_error_stage = None
            content_item.save()
    except Exception as exc:
        content_item.status = ContentStatus.FAILED
        content_item.current_stage = ContentStage.PUBLISH
        content_item.last_error_code = "PUBLISH_FAILED"
        content_item.last_error_message = str(exc)
        content_item.last_error_stage = ContentStage.PUBLISH
        content_item.latest_run_id = run_id
        content_item.save()
        record = PublishRecord.objects.create(
            content_item=content_item,
            channel=PublishChannel.WEB,
            status=PublishStatus.FAILED,
            request_id=request_id,
            run_id=run_id,
            triggered_by=triggered_by,
            triggered_by_user=triggered_by_user,
            error_code="PUBLISH_FAILED",
            error_message=str(exc),
        )
        _finish_run_log(
            log,
            status=RunLogStatus.FAILED,
            error_code="PUBLISH_FAILED",
            error_summary=str(exc),
        )
        raise

    _finish_run_log(
        log,
        status=RunLogStatus.SUCCESS,
        context_json={
            "publish_record_id": str(record.id),
            "content_page_snapshot_id": str(snapshot.id),
            "slug": snapshot.slug,
        },
    )
    return {
        "run_id": str(run_id),
        "publish_record_id": str(record.id),
        "snapshot_id": str(snapshot.id),
        "slug": snapshot.slug,
        "status": content_item.status,
    }


def notify_content_item(
    content_item: ContentItem,
    *,
    email_adapter: BaseEmailAdapter | None = None,
    run_id: uuid.UUID | None = None,
    request_id: str | None = None,
    triggered_by: str = TriggeredBy.SYSTEM,
    triggered_by_user: User | None = None,
    batch_date: date | None = None,
) -> dict[str, Any]:
    run_id = run_id or uuid.uuid4()
    email_adapter = email_adapter or get_email_adapter()
    log = _create_run_log(
        content_item=content_item,
        stage=ContentStage.NOTIFY,
        run_id=run_id,
        request_id=request_id,
        triggered_by=triggered_by,
        triggered_by_user=triggered_by_user,
        retryable=True,
    )
    now = timezone.now()
    effective_batch_date = batch_date or timezone.localdate(content_item.published_at_web or now)

    with transaction.atomic():
        batch, _ = EmailDigestBatch.objects.get_or_create(
            batch_date=effective_batch_date,
            defaults={
                "status": EmailDigestStatus.QUEUED,
                "triggered_by": triggered_by,
                "triggered_by_user": triggered_by_user,
                "request_id": request_id,
                "provider_name": getattr(email_adapter, "provider_name", "mock_email"),
            },
        )
        batch.triggered_by = triggered_by
        batch.triggered_by_user = triggered_by_user
        batch.request_id = request_id
        batch.provider_name = getattr(email_adapter, "provider_name", "mock_email")
        batch.status = EmailDigestStatus.SENDING
        batch.started_at = batch.started_at or now
        batch.save()

        item, _ = EmailDigestBatchItem.objects.get_or_create(
            batch=batch,
            content_item=content_item,
            defaults={"sort_order": batch.items.count() + 1},
        )
        publish_record = PublishRecord.objects.create(
            content_item=content_item,
            channel=PublishChannel.EMAIL_DIGEST,
            status=PublishStatus.QUEUED,
            request_id=request_id,
            run_id=run_id,
            triggered_by=triggered_by,
            triggered_by_user=triggered_by_user,
            email_digest_batch=batch,
            payload_snapshot={"batch_item_id": str(item.id), "batch_date": str(batch.batch_date)},
        )

    sent_count = 0
    failed_count = 0
    active_subscribers = list(Subscriber.objects.filter(status=SubscriberStatus.ACTIVE).order_by("email"))
    for subscriber in active_subscribers:
        delivery, _ = EmailDelivery.objects.get_or_create(
            batch=batch,
            subscriber=subscriber,
            defaults={"status": EmailDeliveryStatus.QUEUED},
        )
        if delivery.status in {EmailDeliveryStatus.SENT, EmailDeliveryStatus.DELIVERED}:
            sent_count += 1
            continue

        subject, html, text = build_digest_email(batch=batch, subscriber=subscriber)
        message = EmailMessage(
            to_email=subscriber.email,
            subject=subject,
            html=html,
            text=text,
            from_email=getattr(settings, "EMAIL_FROM_ADDRESS", "digest@example.com"),
            metadata={
                "batch_key": f"digest-{batch.batch_date.isoformat()}",
                "content_item_id": str(content_item.id),
                "subscriber_id": str(subscriber.id),
            },
        )
        try:
            send_result = email_adapter.send(message)
        except IntegrationError as exc:
            failed_count += 1
            delivery.attempt_no += 1
            delivery.status = EmailDeliveryStatus.FAILED
            delivery.error_code = exc.code
            delivery.error_message = str(exc)
            delivery.save()
            continue

        sent_count += 1
        delivery.status = EmailDeliveryStatus.SENT
        delivery.provider_message_id = send_result.provider_message_id
        delivery.sent_at = now
        delivery.error_code = None
        delivery.error_message = None
        delivery.save()
        subscriber.last_sent_at = now
        subscriber.save(update_fields=["last_sent_at", "updated_at"])
        if send_result.provider_batch_id and not batch.provider_batch_id:
            batch.provider_batch_id = send_result.provider_batch_id

    batch.total_content_count = batch.items.count()
    batch.total_recipient_count = len(active_subscribers)
    batch.sent_count = sent_count
    batch.failed_count = failed_count
    batch.completed_at = now
    if failed_count and sent_count:
        batch.status = EmailDigestStatus.PARTIAL_FAILED
        publish_record.status = PublishStatus.FAILED
        publish_record.error_code = "DIGEST_PARTIAL_FAILED"
        publish_record.error_message = f"{failed_count} deliveries failed"
    elif failed_count:
        batch.status = EmailDigestStatus.FAILED
        publish_record.status = PublishStatus.FAILED
        publish_record.error_code = "DIGEST_FAILED"
        publish_record.error_message = "all deliveries failed"
    else:
        batch.status = EmailDigestStatus.SENT
        publish_record.status = PublishStatus.SUCCESS
        publish_record.published_at = now

    batch.save()
    publish_record.response_snapshot = {
        "sent_count": sent_count,
        "failed_count": failed_count,
        "total_recipient_count": len(active_subscribers),
    }
    publish_record.save()

    content_item.status = ContentStatus.PUBLISHED
    content_item.current_stage = ContentStage.NOTIFY
    content_item.last_processed_at = now
    content_item.latest_run_id = run_id
    content_item.save(update_fields=["status", "current_stage", "last_processed_at", "latest_run_id", "updated_at"])

    if failed_count:
        _finish_run_log(
            log,
            status=RunLogStatus.FAILED,
            error_code="DIGEST_DELIVERY_FAILED",
            error_summary=f"{failed_count} deliveries failed",
            context_json={
                "batch_id": str(batch.id),
                "publish_record_id": str(publish_record.id),
                "sent_count": sent_count,
                "failed_count": failed_count,
            },
        )
    else:
        _finish_run_log(
            log,
            status=RunLogStatus.SUCCESS,
            context_json={
                "batch_id": str(batch.id),
                "publish_record_id": str(publish_record.id),
                "sent_count": sent_count,
                "failed_count": failed_count,
            },
        )

    return {
        "run_id": str(run_id),
        "batch_id": str(batch.id),
        "publish_record_id": str(publish_record.id),
        "batch_status": batch.status,
        "sent_count": sent_count,
        "failed_count": failed_count,
    }


def create_wechat_draft(
    *,
    content_item: ContentItem | None = None,
    adapter: BaseWeChatDraftAdapter | None = None,
    run_id: uuid.UUID | None = None,
    request_id: str | None = None,
    triggered_by: str = TriggeredBy.SYSTEM,
    triggered_by_user: User | None = None,
    manual_title: str | None = None,
    manual_author: str | None = None,
    manual_digest: str | None = None,
    manual_body_html: str | None = None,
    thumb_media_id: str | None = None,
    show_cover_pic: bool = True,
) -> dict[str, Any]:
    adapter = adapter or get_wechat_draft_adapter()
    run_id = run_id or uuid.uuid4()
    now = timezone.now()
    is_manual_input = content_item is None
    content_item = content_item or _create_manual_wechat_content_item(
        title=manual_title,
        author=manual_author,
        digest_text=manual_digest,
        body_markdown=manual_body_html,
    )
    source_mode = WeChatSourceMode.MANUAL_INPUT if is_manual_input else WeChatSourceMode.CONTENT_ITEM
    title = manual_title or getattr(content_item, "title_zh", None) or getattr(content_item, "title_original", None)
    author = manual_author or getattr(content_item, "author_or_speaker", None) or "TechBrief"
    digest_text = manual_digest or getattr(content_item, "summary_zh", None) or getattr(content_item, "summary_original", None) or title
    content_html = manual_body_html or _markdown_to_html(
        getattr(content_item, "zh_md", None) or getattr(content_item, "content_md", None) or title
    )

    if not title:
        raise ValueError("wechat draft title is required")

    payload = WeChatDraftPayload(
        title=title,
        author=author,
        digest=digest_text or title,
        content_html=content_html,
        content_source_url=getattr(content_item, "canonical_url", None) or getattr(content_item, "source_url", None),
        thumb_media_id=thumb_media_id,
        show_cover_pic=show_cover_pic,
        metadata={"content_item_id": str(content_item.id)} if content_item else {},
    )

    publish_record = PublishRecord.objects.create(
        content_item=content_item,
        channel=PublishChannel.WECHAT_DRAFT,
        status=PublishStatus.QUEUED,
        request_id=request_id,
        run_id=run_id,
        triggered_by=triggered_by,
        triggered_by_user=triggered_by_user,
        payload_snapshot={"title": title, "author": author},
    )
    detail = WeChatDraftDetail.objects.create(
        publish_record=publish_record,
        source_mode=source_mode,
        manual_title=manual_title,
        manual_author=manual_author,
        manual_digest=manual_digest,
        body_source_content_item=content_item if source_mode == WeChatSourceMode.CONTENT_ITEM else None,
        thumb_media_id=thumb_media_id,
        show_cover_pic=show_cover_pic,
    )

    try:
        result = adapter.create_draft(payload)
    except IntegrationError as exc:
        publish_record.status = PublishStatus.FAILED
        publish_record.error_code = exc.code
        publish_record.error_message = str(exc)
        publish_record.save()
        detail.retry_count += 1
        detail.last_retry_at = now
        detail.save()
        return {
            "publish_record_id": str(publish_record.id),
            "wechat_detail_id": str(detail.id),
            "status": publish_record.status,
            "error_code": publish_record.error_code,
        }

    publish_record.status = PublishStatus.SUCCESS
    publish_record.external_id = result.draft_id
    publish_record.response_snapshot = result.raw_response
    publish_record.published_at = now
    publish_record.save()
    detail.last_retry_at = now
    detail.save()
    return {
        "publish_record_id": str(publish_record.id),
        "wechat_detail_id": str(detail.id),
        "status": publish_record.status,
        "draft_id": result.draft_id,
    }


def publish_and_notify_content(
    content_item: ContentItem,
    *,
    email_adapter: BaseEmailAdapter | None = None,
    run_id: uuid.UUID | None = None,
    request_id: str | None = None,
    triggered_by: str = TriggeredBy.SYSTEM,
    triggered_by_user: User | None = None,
) -> dict[str, Any]:
    run_id = run_id or uuid.uuid4()
    publish_result = publish_content_item(
        content_item,
        run_id=run_id,
        request_id=request_id,
        triggered_by=triggered_by,
        triggered_by_user=triggered_by_user,
    )
    notify_result = notify_content_item(
        content_item,
        email_adapter=email_adapter,
        run_id=run_id,
        request_id=request_id,
        triggered_by=triggered_by,
        triggered_by_user=triggered_by_user,
    )
    return {"publish": publish_result, "notify": notify_result}


def build_digest_email(*, batch: EmailDigestBatch, subscriber: Subscriber) -> tuple[str, str, str]:
    items = list(
        batch.items.select_related("content_item")
        .order_by("sort_order", "created_at")
        .values_list(
            "content_item__id",
            "content_item__title_zh",
            "content_item__title_original",
            "content_item__web_slug",
        )
    )
    subject = f"TechBrief Daily Digest | {batch.batch_date.isoformat()}"
    unsubscribe_url = build_unsubscribe_url(subscriber.unsubscribe_token)
    tracking_base = build_tracking_pixel_base_url()
    lines_html = []
    lines_text = []
    first_content_id = ""
    for content_item_id, title_zh, title_original, slug in items:
        title = title_zh or title_original
        url = build_public_content_url(slug)
        lines_html.append(f"<li><a href=\"{url}\">{title}</a></li>")
        lines_text.append(f"- {title}: {url}")
        if not first_content_id:
            first_content_id = str(content_item_id)

    tracking_pixel_tag = build_tracking_pixel_tag(tracking_base, subscriber.id, first_content_id)
    html = (
        "<html><body>"
        f"<h1>{subject}</h1>"
        "<p>Today published briefings:</p>"
        f"<ul>{''.join(lines_html)}</ul>"
        f"<p><a href=\"{unsubscribe_url}\">Unsubscribe</a></p>"
        f"{tracking_pixel_tag}"
        "</body></html>"
    )
    text = f"{subject}\n\nToday published briefings:\n" + "\n".join(lines_text) + f"\n\nUnsubscribe: {unsubscribe_url}\n"
    return subject, html, text


def build_public_content_url(slug: str | None) -> str:
    base_url = getattr(settings, "PUBLIC_BASE_URL", "http://127.0.0.1:8010").rstrip("/")
    if not slug:
        return base_url
    return f"{base_url}/articles/{slug}"


def build_unsubscribe_url(token: str) -> str:
    base_url = getattr(settings, "PUBLIC_BASE_URL", "http://127.0.0.1:8010").rstrip("/")
    return f"{base_url}/unsubscribe/{token}"


def build_tracking_pixel_base_url() -> str:
    base_url = getattr(settings, "PUBLIC_BASE_URL", "http://127.0.0.1:8010").rstrip("/")
    return f"{base_url}/api/public/tracking-pixel"


def build_tracking_pixel_tag(tracking_base: str, subscriber_id, content_id: str = "") -> str:
    params = f"?sid={subscriber_id}"
    if content_id:
        params += f"&cid={content_id}"
    return f'<img src="{tracking_base}{params}" width="1" height="1" alt="" style="display:none;" />'


def serialize_datetime(value) -> str | None:
    if not value:
        return None
    return timezone.localtime(value).isoformat()


def _create_run_log(
    *,
    content_item: ContentItem,
    stage: str,
    run_id: uuid.UUID,
    request_id: str | None,
    triggered_by: str,
    triggered_by_user: User | None,
    retryable: bool,
) -> RunLog:
    attempt_no = (
        RunLog.objects.filter(content_item=content_item, stage=stage).count() + 1
    )
    return RunLog.objects.create(
        run_id=run_id,
        request_id=request_id,
        content_item=content_item,
        stage=stage,
        attempt_no=attempt_no,
        status=RunLogStatus.RUNNING,
        triggered_by=triggered_by,
        triggered_by_user=triggered_by_user,
        retryable=retryable,
    )


def _finish_run_log(
    log: RunLog,
    *,
    status: str,
    context_json: dict[str, Any] | None = None,
    error_code: str | None = None,
    error_summary: str | None = None,
) -> None:
    ended_at = timezone.now()
    duration_ms = int((ended_at - log.started_at).total_seconds() * 1000)
    log.status = status
    log.ended_at = ended_at
    log.duration_ms = max(duration_ms, 0)
    log.context_json = context_json or {}
    log.error_code = error_code
    log.error_summary = error_summary
    log.save()


def _resolve_page_kind(content_item: ContentItem) -> str:
    if content_item.content_type == ContentType.VIDEO:
        return PageKind.VIDEO
    return PageKind.ARTICLE


def _build_disclaimer_md(content_item: ContentItem) -> str:
    source_name = content_item.source_name_snapshot or "the original source"
    return f"This is a translated editorial briefing based on content from {source_name}."


def _ensure_content_slug(content_item: ContentItem) -> str:
    if content_item.web_slug:
        return content_item.web_slug

    base_slug = slugify(content_item.title_zh or content_item.title_original) or content_item.dedupe_key[:12]
    candidate = base_slug[:240]
    suffix = 1
    while ContentPageSnapshot.objects.exclude(content_item=content_item).filter(slug=candidate).exists():
        suffix += 1
        candidate = f"{base_slug[:230]}-{suffix}"
    return candidate


def _markdown_to_html(markdown_text: str) -> str:
    lines = [line.strip() for line in markdown_text.splitlines()]
    html_parts: list[str] = []
    for line in lines:
        if not line:
            continue
        if line.startswith("### "):
            html_parts.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("## "):
            html_parts.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("# "):
            html_parts.append(f"<h1>{line[2:]}</h1>")
        else:
            html_parts.append(f"<p>{line}</p>")
    return "".join(html_parts) or f"<p>{striptags(markdown_text)}</p>"


def get_default_mock_email_adapter() -> MockEmailAdapter:
    return MockEmailAdapter()


def get_default_mock_wechat_adapter() -> MockWeChatDraftAdapter:
    return MockWeChatDraftAdapter()


def _create_manual_wechat_content_item(
    *,
    title: str | None,
    author: str | None,
    digest_text: str | None,
    body_markdown: str | None,
) -> ContentItem:
    base_title = title or "Manual WeChat Draft"
    dedupe_key = hashlib.sha256(
        f"manual-wechat|{base_title}|{author or ''}|{digest_text or ''}".encode("utf-8")
    ).hexdigest()
    item, _ = ContentItem.objects.get_or_create(
        dedupe_key=dedupe_key,
        defaults={
            "source_name_snapshot": "Manual WeChat",
            "content_type": ContentType.MANUAL,
            "status": ContentStatus.PUBLISHED,
            "current_stage": ContentStage.PUBLISH,
            "title_original": base_title,
            "title_zh": title or base_title,
            "summary_zh": digest_text,
            "author_or_speaker": author,
            "content_md": body_markdown or base_title,
            "zh_md": body_markdown or base_title,
            "supports_bilingual": False,
            "published_at_web": timezone.now(),
        },
    )
    return item


def retry_wechat_draft(
    *,
    publish_record: PublishRecord,
    request_id: str | None = None,
    triggered_by: str = TriggeredBy.SYSTEM,
    triggered_by_user: User | None = None,
) -> dict[str, Any]:
    """Retry a failed WeChat draft creation."""
    adapter = get_wechat_draft_adapter()
    now = timezone.now()

    detail = publish_record.wechat_detail
    if detail is None:
        raise ValueError("publish record has no wechat_detail")

    payload = WeChatDraftPayload(
        title=detail.manual_title or publish_record.content_item.title_zh or publish_record.content_item.title_original,
        author=detail.manual_author or publish_record.content_item.author_or_speaker or "TechBrief",
        digest=detail.manual_digest or publish_record.content_item.summary_zh or publish_record.content_item.summary_original,
        content_html=_markdown_to_html(
            publish_record.content_item.zh_md or publish_record.content_item.content_md or ""
        ),
        content_source_url=publish_record.content_item.canonical_url or publish_record.content_item.source_url,
        thumb_media_id=detail.thumb_media_id,
        show_cover_pic=detail.show_cover_pic,
        metadata={"content_item_id": str(publish_record.content_item_id), "retry": True},
    )

    detail.retry_count += 1
    detail.last_retry_at = now
    detail.save()

    try:
        result = adapter.create_draft(payload)
    except IntegrationError as exc:
        publish_record.error_code = exc.code
        publish_record.error_message = str(exc)
        publish_record.save()
        return {
            "publish_record_id": str(publish_record.id),
            "status": publish_record.status,
            "error_code": publish_record.error_code,
        }

    publish_record.status = PublishStatus.SUCCESS
    publish_record.external_id = result.draft_id
    publish_record.response_snapshot = result.raw_response
    publish_record.published_at = now
    publish_record.error_code = None
    publish_record.error_message = None
    publish_record.save()
    return {
        "publish_record_id": str(publish_record.id),
        "status": publish_record.status,
        "draft_id": result.draft_id,
    }
