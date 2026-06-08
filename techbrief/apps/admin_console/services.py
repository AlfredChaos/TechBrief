from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import date
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import URLValidator
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from techbrief.apps.content_pipeline.models import (
    ContentItem,
    ContentStage,
    ContentStatus,
    ContentType,
    DiscoveryRun,
    DiscoveryRunStatus,
    DiscoveryRunType,
    EndpointContentScope,
    EndpointRole,
    IngestionMode,
    Source,
    SourceEndpoint,
    SourceType,
    TextSourceStatus,
    TriggeredBy,
)
from techbrief.apps.content_pipeline.tasks import run_discovery, run_fetch, run_notify, run_publish
from techbrief.apps.content_pipeline.tasks import (
    run_extract,
    run_research,
    run_transcribe,
    run_translate,
)
from techbrief.apps.core.models import User
from techbrief.apps.observability.models import RunLog, RunLogStatus
from techbrief.apps.publishers.models import PublishChannel, PublishRecord, Subscriber, WeChatSourceMode
from techbrief.apps.publishers.services import (
    build_public_content_url,
    create_wechat_draft,
    publish_content_item,
    retry_wechat_draft,
)

URL_VALIDATOR = URLValidator()
RETRYABLE_ADMIN_STAGES = {
    ContentStage.FETCH,
    ContentStage.EXTRACT,
    ContentStage.TRANSCRIBE,
    ContentStage.TRANSLATE,
    ContentStage.RESEARCH,
    ContentStage.PUBLISH,
    ContentStage.NOTIFY,
}
STAGE_TASK_MAP = {
    ContentStage.FETCH: run_fetch,
    ContentStage.EXTRACT: run_extract,
    ContentStage.TRANSCRIBE: run_transcribe,
    ContentStage.TRANSLATE: run_translate,
    ContentStage.RESEARCH: run_research,
    ContentStage.PUBLISH: run_publish,
    ContentStage.NOTIFY: run_notify,
}

# Ordered pipeline stages for timeline display in workflow runs.
CONTENT_STAGES = [
    ContentStage.FETCH,
    ContentStage.EXTRACT,
    ContentStage.TRANSCRIBE,
    ContentStage.TRANSLATE,
    ContentStage.RESEARCH,
    ContentStage.REVIEW_PENDING,
    ContentStage.PUBLISH,
    ContentStage.NOTIFY,
]


class AdminActionError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int = 400,
        error_type: str = "ValidationError",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.error_type = error_type
        self.details = details or {}


def parse_page_number(raw_value: str | None, default: int = 1) -> int:
    try:
        value = int(raw_value or default)
    except (TypeError, ValueError):
        return default
    return max(value, 1)


def parse_page_size(raw_value: str | None, default: int = 20, maximum: int = 100) -> int:
    try:
        value = int(raw_value or default)
    except (TypeError, ValueError):
        return default
    return max(1, min(value, maximum))


def serialize_datetime(value):
    if not value:
        return None
    return timezone.localtime(value).isoformat()


def _require_string(payload: dict[str, Any], field: str) -> str:
    value = str(payload.get(field) or "").strip()
    if not value:
        raise AdminActionError(
            "VALIDATION_REQUIRED_FIELD_MISSING",
            f"{field} is required",
            details={"field": field},
        )
    return value


def _validate_url(value: str, *, field: str = "url") -> str:
    try:
        URL_VALIDATOR(value)
    except ValidationError as exc:
        raise AdminActionError(
            "VALIDATION_INVALID_URL",
            f"{field} must be a valid URL",
            details={"field": field},
        ) from exc
    return value


def _hash_parts(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _infer_source_name_from_url(url: str) -> str:
    hostname = urlparse(url).hostname or "Manual Source"
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return hostname or "Manual Source"


def _load_source(source_id: str | None) -> Source | None:
    if not source_id:
        return None
    source = Source.objects.filter(id=source_id).first()
    if source is None:
        raise AdminActionError("SOURCE_NOT_FOUND", "source not found", status=404)
    return source


def _normalize_source_scope(source_ids: list[str]) -> dict[str, Any]:
    if not source_ids:
        return {}
    sources = list(Source.objects.filter(id__in=source_ids).order_by("source_code"))
    if len(sources) != len(set(source_ids)):
        raise AdminActionError(
            "WORKFLOW_SOURCE_SCOPE_INVALID",
            "one or more source ids are invalid",
            details={"source_ids": source_ids},
        )
    return {
        "source_codes": [source.source_code for source in sources],
        "source_ids": [str(source.id) for source in sources],
    }


def _serialize_source(source: Source) -> dict[str, Any]:
    endpoints = source.endpoints.order_by("priority", "created_at")
    return {
        "id": str(source.id),
        "source_code": source.source_code,
        "source_name": source.source_name,
        "source_type": source.source_type,
        "base_url": source.base_url,
        "default_language": source.default_language,
        "is_enabled": source.is_enabled,
        "schedule_cron_expr": source.schedule_cron_expr,
        "notes": source.notes,
        "updated_at": serialize_datetime(source.updated_at),
        "endpoints": [
            {
                "id": str(endpoint.id),
                "endpoint_type": endpoint.endpoint_type,
                "endpoint_role": endpoint.endpoint_role,
                "endpoint_url": endpoint.endpoint_url,
                "content_type_scope": endpoint.content_type_scope,
                "priority": endpoint.priority,
                "is_enabled": endpoint.is_enabled,
                "last_success_at": serialize_datetime(endpoint.last_success_at),
            }
            for endpoint in endpoints
        ],
    }


def _paginate_queryset(queryset, *, page: int, page_size: int) -> tuple[list[Any], dict[str, int]]:
    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(page)
    return list(page_obj.object_list), {
        "page": page_obj.number,
        "page_size": page_size,
        "total": paginator.count,
        "total_pages": paginator.num_pages or 1,
    }


def _paginate_items(items: list[dict[str, Any]], *, page: int, page_size: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
    paginator = Paginator(items, page_size)
    page_obj = paginator.get_page(page)
    return list(page_obj.object_list), {
        "page": page_obj.number,
        "page_size": page_size,
        "total": paginator.count,
        "total_pages": paginator.num_pages or 1,
    }


def get_dashboard_data(target_date: date | None = None) -> dict[str, Any]:
    target_date = target_date or timezone.localdate()

    new_content_today = ContentItem.objects.filter(discovered_at__date=target_date).count()
    published_today = ContentItem.objects.filter(published_at_web__date=target_date).count()
    failed_today = ContentItem.objects.filter(updated_at__date=target_date, status=ContentStatus.FAILED).count()
    subscriber_new_today = Subscriber.objects.filter(subscribed_at__date=target_date).count()
    subscriber_total = Subscriber.objects.count()
    review_pending_count = ContentItem.objects.filter(status=ContentStatus.REVIEW_PENDING).count()

    completed_logs = RunLog.objects.filter(started_at__date=target_date).exclude(status=RunLogStatus.RUNNING)
    completed_total = completed_logs.count()
    completed_success = completed_logs.filter(status=RunLogStatus.SUCCESS).count()
    workflow_success_rate = round(completed_success / completed_total, 4) if completed_total else 0.0

    activities: list[dict[str, Any]] = []
    for item in ContentItem.objects.order_by("-discovered_at")[:4]:
        activities.append(
            {
                "type": "content_discovered",
                "message": f"Discovered {item.title_zh or item.title_original}",
                "occurred_at": item.discovered_at,
                "target_type": "content_item",
                "target_id": str(item.id),
            }
        )
    for subscriber in Subscriber.objects.order_by("-subscribed_at")[:4]:
        activities.append(
            {
                "type": "subscriber_joined",
                "message": f"New subscriber {subscriber.email}",
                "occurred_at": subscriber.subscribed_at,
                "target_type": "subscriber",
                "target_id": str(subscriber.id),
            }
        )
    for log in RunLog.objects.filter(status=RunLogStatus.FAILED).order_by("-started_at")[:4]:
        activities.append(
            {
                "type": "workflow_failed",
                "message": f"Workflow failed at {log.stage}",
                "occurred_at": log.started_at,
                "target_type": "run_log",
                "target_id": str(log.id),
            }
        )

    recent_activities = sorted(
        activities,
        key=lambda activity: activity["occurred_at"] or timezone.make_aware(timezone.datetime.min),
        reverse=True,
    )[:8]

    return {
        "metrics": {
            "new_content_today": new_content_today,
            "published_today": published_today,
            "failed_today": failed_today,
            "subscriber_new_today": subscriber_new_today,
            "subscriber_total": subscriber_total,
            "review_pending_count": review_pending_count,
            "workflow_success_rate": workflow_success_rate,
        },
        "recent_activities": [
            {
                **activity,
                "occurred_at": serialize_datetime(activity["occurred_at"]),
            }
            for activity in recent_activities
        ],
        "system_status": {
            "database": "online",
            "redis": "configured" if getattr(settings, "REDIS_URL", "") else "not_configured",
            "worker": "eager" if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False) else "configured",
        },
    }


def _content_available_actions(item: ContentItem) -> list[str]:
    actions = ["view_detail"]
    if item.status == ContentStatus.REVIEW_PENDING:
        actions.append("publish_web")
    if item.status == ContentStatus.PUBLISHED:
        actions.append("create_wechat_draft")
    if item.status == ContentStatus.FAILED or item.current_stage in {
        ContentStage.FETCH,
        ContentStage.EXTRACT,
        ContentStage.TRANSCRIBE,
        ContentStage.TRANSLATE,
        ContentStage.RESEARCH,
        ContentStage.PUBLISH,
        ContentStage.NOTIFY,
    }:
        actions.append(f"retry_{item.current_stage}")
    if item.web_slug:
        actions.append("open_public_page")
    return actions


def get_source_list_data(params) -> dict[str, Any]:
    queryset = Source.objects.prefetch_related("endpoints").order_by("source_name")
    raw_is_enabled = params.get("is_enabled")
    source_type = (params.get("source_type") or "").strip()

    if raw_is_enabled not in (None, ""):
        normalized = str(raw_is_enabled).strip().lower()
        if normalized not in {"true", "false", "1", "0"}:
            raise AdminActionError(
                "VALIDATION_INVALID_QUERY",
                "is_enabled must be a boolean value",
                details={"field": "is_enabled"},
            )
        queryset = queryset.filter(is_enabled=normalized in {"true", "1"})
    if source_type:
        if source_type not in SourceType.values:
            raise AdminActionError(
                "VALIDATION_INVALID_QUERY",
                "source_type is invalid",
                details={"field": "source_type"},
            )
        queryset = queryset.filter(source_type=source_type)

    return {"items": [_serialize_source(source) for source in queryset]}


def update_source_configuration(*, source_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    source = Source.objects.prefetch_related("endpoints").filter(id=source_id).first()
    if source is None:
        raise AdminActionError("SOURCE_NOT_FOUND", "source not found", status=404)

    update_fields: list[str] = []
    if "is_enabled" in payload:
        source.is_enabled = bool(payload["is_enabled"])
        update_fields.append("is_enabled")
    if "schedule_cron_expr" in payload:
        source.schedule_cron_expr = str(payload["schedule_cron_expr"] or "").strip()
        update_fields.append("schedule_cron_expr")
    if "notes" in payload:
        source.notes = str(payload["notes"] or "").strip() or None
        update_fields.append("notes")
    if update_fields:
        source.save(update_fields=[*update_fields, "updated_at"])

    endpoint_updates = payload.get("endpoints") or []
    for endpoint_payload in endpoint_updates:
        endpoint_id = endpoint_payload.get("id")
        endpoint = source.endpoints.filter(id=endpoint_id).first()
        if endpoint is None:
            raise AdminActionError(
                "VALIDATION_INVALID_BODY",
                "endpoint does not belong to source",
                details={"endpoint_id": endpoint_id},
            )
        endpoint_fields: list[str] = []
        if "is_enabled" in endpoint_payload:
            endpoint.is_enabled = bool(endpoint_payload["is_enabled"])
            endpoint_fields.append("is_enabled")
        if "priority" in endpoint_payload:
            endpoint.priority = int(endpoint_payload["priority"])
            endpoint_fields.append("priority")
        if endpoint_fields:
            endpoint.save(update_fields=[*endpoint_fields, "updated_at"])

    source.refresh_from_db()
    return {
        "id": str(source.id),
        "is_enabled": source.is_enabled,
        "schedule_cron_expr": source.schedule_cron_expr,
        "updated_at": serialize_datetime(source.updated_at),
    }


def get_content_list_data(params) -> dict[str, Any]:
    page = parse_page_number(params.get("page"))
    page_size = parse_page_size(params.get("page_size"))

    queryset = ContentItem.objects.select_related("source")
    query = (params.get("q") or "").strip()
    status = (params.get("status") or "").strip()
    content_type = (params.get("content_type") or "").strip()
    source_id = (params.get("source_id") or "").strip()
    sort = (params.get("sort") or "updated_desc").strip()

    if query:
        queryset = queryset.filter(
            Q(title_original__icontains=query)
            | Q(title_zh__icontains=query)
            | Q(web_slug__icontains=query)
            | Q(source_url__icontains=query)
            | Q(final_url__icontains=query)
            | Q(canonical_url__icontains=query)
        )
    if status:
        queryset = queryset.filter(status=status)
    if content_type:
        queryset = queryset.filter(content_type=content_type)
    if source_id:
        queryset = queryset.filter(source_id=source_id)

    order_map = {
        "published_desc": ["-published_at_source", "-updated_at"],
        "updated_desc": ["-updated_at"],
        "status_asc": ["status", "-updated_at"],
    }
    queryset = queryset.order_by(*order_map.get(sort, order_map["updated_desc"]))
    items, pagination = _paginate_queryset(queryset, page=page, page_size=page_size)

    return {
        "items": [
            {
                "id": str(item.id),
                "content_type": item.content_type,
                "ingestion_mode": item.ingestion_mode,
                "source_name": item.source_name_snapshot,
                "title_original": item.title_original,
                "title_zh": item.title_zh,
                "status": item.status,
                "current_stage": item.current_stage,
                "published_at_source": serialize_datetime(item.published_at_source),
                "updated_at": serialize_datetime(item.updated_at),
                "preview_url": f"/articles/{item.web_slug}" if item.web_slug else None,
                "available_actions": _content_available_actions(item),
            }
            for item in items
        ],
        "pagination": pagination,
    }


def get_content_detail_data(content_item_id: str) -> dict[str, Any]:
    content_item = ContentItem.objects.select_related("source").filter(id=content_item_id).first()
    if content_item is None:
        raise AdminActionError("CONTENT_NOT_FOUND", "content item not found", status=404)

    artifacts = content_item.artifacts.order_by("artifact_type", "created_at")
    run_logs = content_item.run_logs.select_related("triggered_by_user").order_by("-created_at")
    publish_records = (
        content_item.publish_records.select_related("triggered_by_user", "wechat_detail")
        .order_by("-created_at")
    )

    preview_url = build_public_content_url(content_item.web_slug) if content_item.web_slug else None
    return {
        "content": {
            "id": str(content_item.id),
            "content_type": content_item.content_type,
            "ingestion_mode": content_item.ingestion_mode,
            "status": content_item.status,
            "current_stage": content_item.current_stage,
            "source_id": str(content_item.source_id) if content_item.source_id else None,
            "source_name": content_item.source_name_snapshot,
            "title_original": content_item.title_original,
            "title_zh": content_item.title_zh,
            "summary_original": content_item.summary_original,
            "summary_zh": content_item.summary_zh,
            "author_or_speaker": content_item.author_or_speaker,
            "source_url": content_item.source_url,
            "final_url": content_item.final_url,
            "canonical_url": content_item.canonical_url,
            "source_item_id": content_item.source_item_id,
            "published_at_source": serialize_datetime(content_item.published_at_source),
            "published_at_web": serialize_datetime(content_item.published_at_web),
            "content_md": content_item.content_md,
            "zh_md": content_item.zh_md,
            "research_report_md": content_item.research_report_md,
            "transcript_text": content_item.transcript_text,
            "text_source_status": content_item.text_source_status,
            "supports_bilingual": content_item.supports_bilingual,
            "web_slug": content_item.web_slug,
            "metadata_json": content_item.metadata_json or {},
            "available_actions": _content_available_actions(content_item),
            "updated_at": serialize_datetime(content_item.updated_at),
        },
        "artifacts": [
            {
                "id": str(artifact.id),
                "artifact_type": artifact.artifact_type,
                "storage_key": artifact.storage_key,
                "content_type": artifact.content_type,
                "language": artifact.language,
                "size_bytes": artifact.size_bytes,
                "is_primary": artifact.is_primary,
                "created_at": serialize_datetime(artifact.created_at),
            }
            for artifact in artifacts
        ],
        "run_logs": [
            {
                "id": str(log.id),
                "run_id": str(log.run_id),
                "stage": log.stage,
                "attempt_no": log.attempt_no,
                "status": log.status,
                "duration_ms": log.duration_ms,
                "error_code": log.error_code,
                "error_summary": log.error_summary,
                "retryable": log.retryable,
                "triggered_by": log.triggered_by,
                "triggered_by_user": log.triggered_by_user.display_name if log.triggered_by_user else None,
                "started_at": serialize_datetime(log.started_at),
                "ended_at": serialize_datetime(log.ended_at),
                "context_json": log.context_json or {},
            }
            for log in run_logs
        ],
        "publish_records": [
            {
                "id": str(record.id),
                "channel": record.channel,
                "status": record.status,
                "external_id": record.external_id,
                "published_at": serialize_datetime(record.published_at),
                "error_code": record.error_code,
                "error_message": record.error_message,
                "request_snapshot": record.payload_snapshot or {},
                "response_snapshot": record.response_snapshot or {},
                "retry_count": getattr(record.wechat_detail, "retry_count", 0) if hasattr(record, "wechat_detail") else 0,
            }
            for record in publish_records
        ],
        "preview": {
            "mode": "public" if preview_url else "admin_console",
            "url": preview_url or reverse("admin_console:content-detail", args=[content_item.id]),
        },
    }


def queue_manual_url_import(
    *,
    payload: dict[str, Any],
    request_id: str | None,
    triggered_by_user: User | None,
) -> dict[str, Any]:
    url = _validate_url(_require_string(payload, "url"))
    source = _load_source(payload.get("source_id"))
    source_name = str(payload.get("source_name") or "").strip() or (source.source_name if source else _infer_source_name_from_url(url))
    force_reimport = bool(payload.get("force_reimport"))
    dedupe_key = _hash_parts("manual_url", str(source.id) if source else source_name.lower(), url)
    run_id = uuid4()

    content_item = ContentItem.objects.filter(dedupe_key=dedupe_key).first()
    if content_item and not force_reimport:
        return {
            "content_item_id": str(content_item.id),
            "status": content_item.status,
            "current_stage": content_item.current_stage,
            "run_id": str(content_item.latest_run_id or run_id),
            "reused": True,
        }

    metadata_json = dict(content_item.metadata_json or {}) if content_item else {}
    metadata_json["manual_intake"] = {
        "mode": IngestionMode.MANUAL_URL,
        "requested_at": timezone.now().isoformat(),
        "requested_by_user_id": str(triggered_by_user.id) if triggered_by_user else None,
    }
    defaults = {
        "source": source,
        "source_name_snapshot": source_name,
        "content_type": ContentType.ARTICLE,
        "ingestion_mode": IngestionMode.MANUAL_URL,
        "status": ContentStatus.PROCESSING,
        "current_stage": ContentStage.FETCH,
        "title_original": content_item.title_original if content_item else url,
        "source_url": url,
        "final_url": url,
        "canonical_url": url,
        "original_language": source.default_language if source else "en",
        "latest_run_id": run_id,
        "last_processed_at": timezone.now(),
        "metadata_json": metadata_json,
    }
    if content_item is None:
        content_item = ContentItem.objects.create(dedupe_key=dedupe_key, **defaults)
    else:
        for field_name, value in defaults.items():
            setattr(content_item, field_name, value)
        content_item.save()

    run_fetch.delay(
        content_item_id=str(content_item.id),
        run_id=str(run_id),
        request_id=request_id,
        triggered_by=TriggeredBy.ADMIN_USER,
        triggered_by_user_id=str(triggered_by_user.id) if triggered_by_user else None,
    )
    return {
        "content_item_id": str(content_item.id),
        "status": ContentStatus.PROCESSING,
        "current_stage": ContentStage.FETCH,
        "run_id": str(run_id),
        "reused": False,
    }


def create_manual_content(*, payload: dict[str, Any], triggered_by_user: User | None) -> dict[str, Any]:
    content_type = str(payload.get("content_type") or "").strip() or ContentType.MANUAL
    if content_type not in {ContentType.ARTICLE, ContentType.MANUAL}:
        raise AdminActionError(
            "VALIDATION_INVALID_BODY",
            "content_type must be article or manual",
            details={"field": "content_type"},
        )

    source = _load_source(payload.get("source_id"))
    source_name = str(payload.get("source_name") or "").strip() or (source.source_name if source else "")
    if not source_name:
        raise AdminActionError(
            "VALIDATION_REQUIRED_FIELD_MISSING",
            "source_name is required",
            details={"field": "source_name"},
        )

    canonical_url = str(payload.get("canonical_url") or "").strip() or None
    if canonical_url:
        canonical_url = _validate_url(canonical_url, field="canonical_url")

    published_at_source = parse_datetime(str(payload.get("published_at_source") or "").strip()) if payload.get("published_at_source") else None
    base_fingerprint = _hash_parts(
        "manual_rich_text",
        source_name.lower(),
        _require_string(payload, "title_original"),
        _require_string(payload, "title_zh"),
        canonical_url or "",
    )
    content_item = ContentItem.objects.create(
        source=source,
        source_name_snapshot=source_name,
        content_type=content_type,
        ingestion_mode=IngestionMode.MANUAL_RICH_TEXT,
        status=ContentStatus.REVIEW_PENDING,
        current_stage=ContentStage.REVIEW_PENDING,
        title_original=_require_string(payload, "title_original"),
        title_zh=_require_string(payload, "title_zh"),
        summary_original=str(payload.get("summary_original") or "").strip() or None,
        summary_zh=str(payload.get("summary_zh") or "").strip() or None,
        author_or_speaker=str(payload.get("author_or_speaker") or "").strip() or None,
        source_url=canonical_url,
        canonical_url=canonical_url,
        dedupe_key=base_fingerprint,
        published_at_source=published_at_source,
        original_language=source.default_language if source else "en",
        text_source_status=TextSourceStatus.MANUAL_INPUT,
        content_md=_require_string(payload, "body_original_md"),
        zh_md=_require_string(payload, "body_zh_md"),
        supports_bilingual=bool(payload.get("supports_bilingual", True)),
        last_processed_at=timezone.now(),
        latest_run_id=uuid4(),
        metadata_json={
            "manual_intake": {
                "mode": IngestionMode.MANUAL_RICH_TEXT,
                "created_by_user_id": str(triggered_by_user.id) if triggered_by_user else None,
            }
        },
    )
    return {
        "content_item_id": str(content_item.id),
        "status": content_item.status,
        "current_stage": content_item.current_stage,
    }


def retry_content_stage(
    *,
    content_item_id: str,
    payload: dict[str, Any],
    request_id: str | None,
    triggered_by_user: User | None,
) -> dict[str, Any]:
    stage = str(payload.get("stage") or "").strip()
    if stage not in RETRYABLE_ADMIN_STAGES:
        raise AdminActionError(
            "PIPELINE_STAGE_NOT_RETRYABLE",
            "stage is not retryable",
            details={"stage": stage},
        )

    content_item = ContentItem.objects.filter(id=content_item_id).first()
    if content_item is None:
        raise AdminActionError("CONTENT_NOT_FOUND", "content item not found", status=404)

    run_id = uuid4()
    content_item.status = ContentStatus.PROCESSING if stage != ContentStage.NOTIFY else ContentStatus.PUBLISHED
    content_item.current_stage = stage
    content_item.latest_run_id = run_id
    content_item.last_processed_at = timezone.now()
    content_item.save(
        update_fields=[
            "status",
            "current_stage",
            "latest_run_id",
            "last_processed_at",
            "updated_at",
        ]
    )
    STAGE_TASK_MAP[stage].delay(
        content_item_id=str(content_item.id),
        run_id=str(run_id),
        request_id=request_id,
        triggered_by=TriggeredBy.SYSTEM_RETRY,
        triggered_by_user_id=str(triggered_by_user.id) if triggered_by_user else None,
    )
    return {
        "content_item_id": str(content_item.id),
        "stage": stage,
        "run_id": str(run_id),
        "status": "queued",
    }


def publish_content_web(
    *,
    content_item_id: str,
    payload: dict[str, Any],
    request_id: str | None,
    triggered_by_user: User | None,
) -> dict[str, Any]:
    content_item = ContentItem.objects.filter(id=content_item_id).first()
    if content_item is None:
        raise AdminActionError("CONTENT_NOT_FOUND", "content item not found", status=404)
    if content_item.status not in {ContentStatus.REVIEW_PENDING, ContentStatus.PUBLISHED, ContentStatus.FAILED}:
        raise AdminActionError("CONTENT_NOT_READY_FOR_PUBLISH", "content item is not ready for publish", status=409)

    result = publish_content_item(
        content_item,
        request_id=request_id,
        triggered_by=TriggeredBy.ADMIN_USER,
        triggered_by_user=triggered_by_user,
        slug=str(payload.get("slug") or "").strip() or None,
        seo_title=str(payload.get("seo_title") or "").strip() or None,
        seo_description=str(payload.get("seo_description") or "").strip() or None,
    )
    return {
        "content_item_id": str(content_item.id),
        "publish_record_id": result["publish_record_id"],
        "status": ContentStatus.PUBLISHED,
        "slug": result["slug"],
        "url": build_public_content_url(result["slug"]),
        "published_at": result["published_at"],
    }


def trigger_discovery(
    *,
    payload: dict[str, Any],
    request_id: str | None,
    triggered_by_user: User | None,
) -> dict[str, Any]:
    source_scope = _normalize_source_scope(payload.get("source_ids") or [])
    discovery_run = DiscoveryRun.objects.create(
        run_type=DiscoveryRunType.MANUAL,
        status=DiscoveryRunStatus.QUEUED,
        request_id=request_id,
        triggered_by=TriggeredBy.ADMIN_USER,
        triggered_by_user=triggered_by_user,
        source_scope=source_scope,
    )
    run_discovery.delay(discovery_run_id=str(discovery_run.id))
    return {
        "discovery_run_id": str(discovery_run.id),
        "run_id": str(discovery_run.run_id),
        "status": discovery_run.status,
    }


def create_wechat_draft_from_payload(
    *,
    payload: dict[str, Any],
    request_id: str | None,
    triggered_by_user: User | None,
) -> dict[str, Any]:
    source_mode = str(payload.get("source_mode") or "").strip()
    if source_mode not in {WeChatSourceMode.CONTENT_ITEM, WeChatSourceMode.MANUAL_INPUT}:
        raise AdminActionError(
            "VALIDATION_INVALID_BODY",
            "source_mode is invalid",
            details={"field": "source_mode"},
        )

    if source_mode == WeChatSourceMode.CONTENT_ITEM:
        content_item_id = _require_string(payload, "content_item_id")
        content_item = ContentItem.objects.filter(id=content_item_id).first()
        if content_item is None:
            raise AdminActionError("CONTENT_NOT_FOUND", "content item not found", status=404)
        if content_item.status != ContentStatus.PUBLISHED:
            raise AdminActionError("CONTENT_NOT_PUBLISHED", "content item must be published first", status=409)
        result = create_wechat_draft(
            content_item=content_item,
            request_id=request_id,
            triggered_by=TriggeredBy.ADMIN_USER,
            triggered_by_user=triggered_by_user,
            thumb_media_id=str(payload.get("thumb_media_id") or "").strip() or None,
            show_cover_pic=bool(payload.get("show_cover_pic", True)),
        )
    else:
        result = create_wechat_draft(
            request_id=request_id,
            triggered_by=TriggeredBy.ADMIN_USER,
            triggered_by_user=triggered_by_user,
            manual_title=_require_string(payload, "title"),
            manual_author=str(payload.get("author") or "").strip() or None,
            manual_digest=str(payload.get("digest") or "").strip() or None,
            manual_body_html=_require_string(payload, "body_html"),
            thumb_media_id=str(payload.get("thumb_media_id") or "").strip() or None,
            show_cover_pic=bool(payload.get("show_cover_pic", True)),
        )

    publish_record = PublishRecord.objects.get(id=result["publish_record_id"])
    return {
        "publish_record_id": str(publish_record.id),
        "wechat_draft_id": publish_record.external_id,
        "status": publish_record.status,
        "created_at": serialize_datetime(publish_record.created_at),
        "error_code": publish_record.error_code,
        "request_snapshot": publish_record.payload_snapshot or {},
        "response_snapshot": publish_record.response_snapshot or {},
    }


def retry_wechat_publish_record(
    *,
    publish_record_id: str,
    request_id: str | None,
    triggered_by_user: User | None,
) -> dict[str, Any]:
    publish_record = PublishRecord.objects.select_related("content_item", "wechat_detail").filter(
        id=publish_record_id,
        channel=PublishChannel.WECHAT_DRAFT,
    ).first()
    if publish_record is None:
        raise AdminActionError("PUBLISH_RECORD_NOT_FOUND", "publish record not found", status=404)
    if publish_record.status != "failed":
        raise AdminActionError("WECHAT_DRAFT_NOT_RETRYABLE", "wechat draft is not retryable", status=409)

    result = retry_wechat_draft(
        publish_record=publish_record,
        request_id=request_id,
        triggered_by=TriggeredBy.ADMIN_USER,
        triggered_by_user=triggered_by_user,
    )
    refreshed_record = PublishRecord.objects.get(id=result["publish_record_id"])
    detail = refreshed_record.wechat_detail
    return {
        "publish_record_id": str(refreshed_record.id),
        "status": refreshed_record.status,
        "retry_count": detail.retry_count,
        "updated_at": serialize_datetime(detail.last_retry_at or refreshed_record.updated_at),
        "error_code": refreshed_record.error_code,
    }


def get_workflow_run_timeline(run_id: str) -> dict:
    """Aggregate per-stage status for a single workflow run."""
    logs = RunLog.objects.filter(run_id=run_id).order_by("started_at")
    if not logs:
        raise AdminActionError("RUN_NOT_FOUND", "run not found", status=404)

    by_stage: dict[str, RunLog] = {}
    for log in logs:
        existing = by_stage.get(log.stage)
        if not existing or log.started_at >= existing.started_at:
            by_stage[log.stage] = log

    first = logs.first()
    timeline = []
    for stage in CONTENT_STAGES:
        log = by_stage.get(stage)
        if log:
            duration = ""
            if log.started_at and log.ended_at:
                duration = f"{(log.ended_at - log.started_at).total_seconds():.1f}s"
            timeline.append({
                "stage": log.stage,
                "status": log.status,
                "started_at": serialize_datetime(log.started_at),
                "ended_at": serialize_datetime(log.ended_at),
                "duration": duration,
                "retry_count": log.retry_count,
                "error_summary": log.error_summary or "",
            })
        else:
            timeline.append({
                "stage": stage,
                "status": "pending",
                "started_at": None,
                "ended_at": None,
                "duration": "",
                "retry_count": 0,
                "error_summary": "",
            })

    total_seconds = 0.0
    started = first.started_at if first else None
    last_ended = logs.last().ended_at if logs.last() else None
    if started and last_ended:
        total_seconds = (last_ended - started).total_seconds()

    return {
        "run_id": str(run_id),
        "total_duration": f"{total_seconds:.1f}s" if total_seconds else "",
        "timeline": timeline,
    }


def retry_workflow_run_stage(
    *,
    run_id: str,
    stage: str,
    request_id: str | None,
    triggered_by_user: User | None,
) -> dict[str, Any]:
    if stage not in RETRYABLE_ADMIN_STAGES:
        raise AdminActionError(
            "PIPELINE_STAGE_NOT_RETRYABLE",
            "stage is not retryable",
            details={"stage": stage},
        )

    log = RunLog.objects.filter(run_id=run_id).first()
    if not log:
        raise AdminActionError("RUN_NOT_FOUND", "run not found", status=404)

    content_item = log.content_item
    if content_item is None:
        raise AdminActionError("CONTENT_NOT_FOUND", "content item not found", status=404)

    new_run_id = uuid4()
    content_item.status = ContentStatus.PROCESSING if stage != ContentStage.NOTIFY else ContentStatus.PUBLISHED
    content_item.current_stage = stage
    content_item.latest_run_id = new_run_id
    content_item.last_processed_at = timezone.now()
    content_item.save(
        update_fields=[
            "status",
            "current_stage",
            "latest_run_id",
            "last_processed_at",
            "updated_at",
        ]
    )
    STAGE_TASK_MAP[stage].delay(
        content_item_id=str(content_item.id),
        run_id=str(new_run_id),
        request_id=request_id,
        triggered_by=TriggeredBy.SYSTEM_RETRY,
        triggered_by_user_id=str(triggered_by_user.id) if triggered_by_user else None,
    )
    return {
        "content_item_id": str(content_item.id),
        "stage": stage,
        "run_id": str(new_run_id),
        "status": "queued",
    }


def get_subscriber_list_data(params) -> dict[str, Any]:
    page = parse_page_number(params.get("page"))
    page_size = parse_page_size(params.get("page_size"))

    queryset = Subscriber.objects.all()
    query = (params.get("q") or "").strip()
    status = (params.get("status") or "").strip()
    sort = (params.get("sort") or "subscribed_desc").strip()

    if query:
        queryset = queryset.filter(email__icontains=query)
    if status:
        queryset = queryset.filter(status=status)

    order_map = {
        "subscribed_desc": ["-subscribed_at"],
        "subscribed_asc": ["subscribed_at"],
    }
    queryset = queryset.order_by(*order_map.get(sort, order_map["subscribed_desc"]))
    items, pagination = _paginate_queryset(queryset, page=page, page_size=page_size)

    return {
        "items": [
            {
                "id": str(item.id),
                "email": item.email,
                "status": item.status,
                "source_page": item.source_page,
                "subscribed_at": serialize_datetime(item.subscribed_at),
                "unsubscribed_at": serialize_datetime(item.unsubscribed_at),
                "last_sent_at": serialize_datetime(item.last_sent_at),
            }
            for item in items
        ],
        "pagination": pagination,
    }


def get_workflow_run_list_data(params) -> dict[str, Any]:
    page = parse_page_number(params.get("page"))
    page_size = parse_page_size(params.get("page_size"))

    logs = RunLog.objects.select_related("content_item", "discovery_run").order_by("-started_at", "-created_at")

    status = (params.get("status") or "").strip()
    stage = (params.get("stage") or "").strip()
    content_item_id = (params.get("content_item_id") or "").strip()
    if status:
        logs = logs.filter(status=status)
    if stage:
        logs = logs.filter(stage=stage)
    if content_item_id:
        logs = logs.filter(content_item_id=content_item_id)

    aggregated: dict[str, dict[str, Any]] = {}
    for log in logs:
        run_key = str(log.run_id)
        row = aggregated.setdefault(
            run_key,
            {
                "run_id": run_key,
                "discovery_run_id": str(log.discovery_run_id) if log.discovery_run_id else None,
                "content_item_id": str(log.content_item_id) if log.content_item_id else None,
                "status": log.status,
                "stage": log.stage,
                "duration_ms": 0,
                "error_code": log.error_code,
                "started_at": log.started_at,
                "ended_at": log.ended_at,
            },
        )

        row["duration_ms"] += log.duration_ms or 0
        row["started_at"] = min(filter(None, [row["started_at"], log.started_at]), default=row["started_at"])
        row["ended_at"] = max(filter(None, [row["ended_at"], log.ended_at]), default=row["ended_at"])
        if not row["content_item_id"] and log.content_item_id:
            row["content_item_id"] = str(log.content_item_id)
        if not row["discovery_run_id"] and log.discovery_run_id:
            row["discovery_run_id"] = str(log.discovery_run_id)
        if log.status == RunLogStatus.FAILED:
            row["status"] = RunLogStatus.FAILED
            row["error_code"] = log.error_code or row["error_code"]
        elif row["status"] != RunLogStatus.FAILED:
            row["status"] = log.status
        if log.started_at and row["started_at"] == log.started_at:
            row["stage"] = log.stage

    items = sorted(aggregated.values(), key=lambda item: item["started_at"] or timezone.make_aware(timezone.datetime.min), reverse=True)
    paginated_items, pagination = _paginate_items(items, page=page, page_size=page_size)

    return {
        "items": [
            {
                **item,
                "started_at": serialize_datetime(item["started_at"]),
                "ended_at": serialize_datetime(item["ended_at"]),
            }
            for item in paginated_items
        ],
        "summary": {
            "total_runs": len(items),
            "success_runs": sum(1 for item in items if item["status"] == RunLogStatus.SUCCESS),
            "failed_runs": sum(1 for item in items if item["status"] == RunLogStatus.FAILED),
        },
        "pagination": pagination,
    }


def get_dashboard_page_context() -> dict[str, Any]:
    return {"dashboard_data": get_dashboard_data()}


def get_source_page_context(params) -> dict[str, Any]:
    return {
        "filters": {
            "is_enabled": params.get("is_enabled", ""),
            "source_type": params.get("source_type", ""),
        },
        "source_data": get_source_list_data(params),
        "source_type_choices": Source._meta.get_field("source_type").choices,
    }


def get_content_page_context(params) -> dict[str, Any]:
    return {
        "filters": {
            "q": params.get("q", ""),
            "status": params.get("status", ""),
            "content_type": params.get("content_type", ""),
            "source_id": params.get("source_id", ""),
        },
        "content_data": get_content_list_data(params),
        "status_choices": ContentItem._meta.get_field("status").choices,
        "content_type_choices": ContentItem._meta.get_field("content_type").choices,
        "source_choices": Source.objects.order_by("source_name").values_list("id", "source_name"),
    }


def get_subscriber_page_context(params) -> dict[str, Any]:
    return {
        "filters": {
            "q": params.get("q", ""),
            "status": params.get("status", ""),
        },
        "subscriber_data": get_subscriber_list_data(params),
        "status_choices": Subscriber._meta.get_field("status").choices,
    }


def get_workflow_page_context(params) -> dict[str, Any]:
    return {
        "filters": {
            "status": params.get("status", ""),
            "stage": params.get("stage", ""),
        },
        "workflow_data": get_workflow_run_list_data(params),
        "status_choices": RunLog._meta.get_field("status").choices,
        "stage_choices": RunLog._meta.get_field("stage").choices,
    }


def get_content_detail_page_context(content_item_id: str) -> dict[str, Any]:
    return {"content_detail_data": get_content_detail_data(content_item_id)}


def get_manual_publish_page_context() -> dict[str, Any]:
    recent_published_items = (
        ContentItem.objects.filter(status=ContentStatus.PUBLISHED)
        .order_by("-published_at_web", "-updated_at")[:8]
    )
    recent_wechat_records = (
        PublishRecord.objects.select_related("content_item", "wechat_detail")
        .filter(channel=PublishChannel.WECHAT_DRAFT)
        .order_by("-created_at")[:8]
    )
    return {
        "published_items": recent_published_items,
        "recent_wechat_records": recent_wechat_records,
        "source_choices": Source.objects.order_by("source_name"),
        "wechat_source_mode_choices": WeChatSourceMode.choices,
    }


def build_navigation(active_name: str) -> list[dict[str, Any]]:
    items = [
        ("dashboard", "Dashboard", reverse("admin_console:dashboard")),
        ("sources", "Sources", reverse("admin_console:sources")),
        ("content", "Content", reverse("admin_console:content")),
        ("subscribers", "Subscribers", reverse("admin_console:subscribers")),
        ("workflow", "Workflow", reverse("admin_console:workflow")),
        ("manual_intake", "Manual Intake", reverse("admin_console:manual-intake")),
        ("manual_publish", "Manual Publish", reverse("admin_console:manual-publish")),
    ]
    return [
        {
            "name": name,
            "label": label,
            "url": url,
            "active": name == active_name,
        }
        for name, label, url in items
    ]


# ---- Source CRUD ----

def get_source_detail_data(source_id: str) -> dict[str, Any]:
    """Return full source detail including endpoints and discovery stats."""
    from techbrief.apps.content_pipeline.models import DiscoveryRunSourceStat

    source = Source.objects.prefetch_related("endpoints").filter(id=source_id).first()
    if source is None:
        raise AdminActionError("SOURCE_NOT_FOUND", "source not found", status=404)

    content_count = ContentItem.objects.filter(source_id=source_id).count()
    recent_runs = DiscoveryRunSourceStat.objects.filter(source_id=source_id).select_related("discovery_run").order_by("-created_at")[:5]

    return {
        **_serialize_source(source),
        "content_count": content_count,
        "recent_discovery_runs": [
            {
                "run_id": str(stat.discovery_run.run_id),
                "status": stat.discovery_run.status,
                "new_count": stat.new_count,
                "updated_count": stat.updated_count,
                "failed_count": stat.failed_count,
                "created_at": serialize_datetime(stat.created_at),
            }
            for stat in recent_runs
        ],
    }


def create_source(*, payload: dict[str, Any], triggered_by_user: User | None) -> dict[str, Any]:
    """Create a new Source with optional endpoints."""
    source_code = _require_string(payload, "source_code")
    if Source.objects.filter(source_code=source_code).exists():
        raise AdminActionError("SOURCE_CODE_DUPLICATE", "source_code already exists", status=409, details={"field": "source_code"})

    source_name = _require_string(payload, "source_name")
    source = Source.objects.create(
        source_code=source_code,
        source_name=source_name,
        source_type=str(payload.get("source_type") or SourceType.OFFICIAL_SITE).strip(),
        base_url=str(payload.get("base_url") or "").strip() or None,
        default_language=str(payload.get("default_language") or "en").strip(),
        is_enabled=bool(payload.get("is_enabled", True)),
        schedule_cron_expr=str(payload.get("schedule_cron_expr") or "0 2 * * *").strip(),
        notes=str(payload.get("notes") or "").strip() or None,
    )

    endpoints = payload.get("endpoints") or []
    for ep in endpoints:
        SourceEndpoint.objects.create(
            source=source,
            endpoint_type=_require_string(ep, "endpoint_type"),
            endpoint_url=_require_string(ep, "endpoint_url"),
            endpoint_role=str(ep.get("endpoint_role") or EndpointRole.PRIMARY).strip(),
            content_type_scope=str(ep.get("content_type_scope") or EndpointContentScope.MIXED).strip(),
            priority=int(ep.get("priority", 100)),
            parser_config=ep.get("parser_config"),
            is_enabled=bool(ep.get("is_enabled", True)),
        )

    return _serialize_source(source)


def delete_source(*, source_id: str) -> dict[str, Any]:
    """Soft-disable a source and delete its endpoints."""
    source = Source.objects.filter(id=source_id).first()
    if source is None:
        raise AdminActionError("SOURCE_NOT_FOUND", "source not found", status=404)

    source.endpoints.all().delete()
    source.is_enabled = False
    source.notes = (source.notes or "") + "\n[Deleted by admin]"
    source.save(update_fields=["is_enabled", "notes", "updated_at"])

    return {"id": str(source.id), "source_code": source.source_code, "status": "disabled"}
