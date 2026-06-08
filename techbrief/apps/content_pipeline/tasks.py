from __future__ import annotations

import json
import uuid
from pathlib import Path

from celery import shared_task
from django.utils import timezone

from techbrief.apps.content_pipeline.models import (
    ContentItem,
    ContentStage,
    ContentStatus,
    ContentType,
    IngestionMode,
    Source,
    TriggeredBy,
)
from techbrief.apps.content_pipeline.services import (
    ContentPipelineService,
    DiscoveryWorkflowService,
    PipelineStageError,
)
from techbrief.apps.integrations.adapters import BaseEmailAdapter, BaseWeChatDraftAdapter
from techbrief.apps.publishers.models import Subscriber, SubscriberSourcePage, SubscriberStatus
from techbrief.apps.publishers.services import (
    create_wechat_draft,
    notify_content_item,
    publish_content_item,
)

STAGE_TASK_MAP = {
    ContentStage.FETCH: "techbrief.content_pipeline.fetch",
    ContentStage.EXTRACT: "techbrief.content_pipeline.extract",
    ContentStage.TRANSCRIBE: "techbrief.content_pipeline.transcribe",
    ContentStage.TRANSLATE: "techbrief.content_pipeline.translate",
    ContentStage.RESEARCH: "techbrief.content_pipeline.research",
    ContentStage.REVIEW_PENDING: "techbrief.content_pipeline.review_pending",
    ContentStage.PUBLISH: "techbrief.content_pipeline.publish",
    ContentStage.NOTIFY: "techbrief.content_pipeline.notify",
}


@shared_task(name="techbrief.content_pipeline.noop")
def noop() -> dict:
    return {"status": "ok"}


def _enqueue_stage(
    *,
    stage: str | None,
    content_item_id: str,
    run_id: str,
    discovery_run_id: str | None,
    request_id: str | None,
    triggered_by: str,
    triggered_by_user_id: str | None,
) -> None:
    if not stage:
        return
    task_name = STAGE_TASK_MAP[stage]
    shared_task = _STAGE_TASK_FUNCS[task_name]
    shared_task.delay(
        content_item_id=content_item_id,
        run_id=run_id,
        discovery_run_id=discovery_run_id,
        request_id=request_id,
        triggered_by=triggered_by,
        triggered_by_user_id=triggered_by_user_id,
    )


def _run_stage_task(
    *,
    content_item_id: str,
    stage: str,
    run_id: str | None = None,
    discovery_run_id: str | None = None,
    request_id: str | None = None,
    triggered_by: str = "system",
    triggered_by_user_id: str | None = None,
) -> dict:
    result = ContentPipelineService.run_stage(
        content_item_id=content_item_id,
        stage=stage,
        run_id=run_id,
        discovery_run_id=discovery_run_id,
        request_id=request_id,
        triggered_by=triggered_by,
        triggered_by_user_id=triggered_by_user_id,
    )
    _enqueue_stage(
        stage=result["next_stage"],
        content_item_id=result["content_item_id"],
        run_id=result["run_id"],
        discovery_run_id=discovery_run_id,
        request_id=request_id,
        triggered_by=triggered_by,
        triggered_by_user_id=triggered_by_user_id,
    )
    return result


@shared_task(name="techbrief.content_pipeline.discover")
def run_discovery(
    *,
    discovery_run_id: str,
) -> dict:
    result = DiscoveryWorkflowService.run(discovery_run_id=discovery_run_id)
    for content_item_id in result["content_item_ids"]:
        run_fetch.delay(
            content_item_id=content_item_id,
            run_id=result["run_id"],
            discovery_run_id=result["discovery_run_id"],
        )
    return result


@shared_task(
    name="techbrief.content_pipeline.fetch",
    autoretry_for=(PipelineStageError,),
    retry_backoff=60,
    retry_backoff_max=600,
    max_retries=3,
)
def run_fetch(
    *,
    content_item_id: str,
    run_id: str | None = None,
    discovery_run_id: str | None = None,
    request_id: str | None = None,
    triggered_by: str = "system",
    triggered_by_user_id: str | None = None,
) -> dict:
    return _run_stage_task(
        content_item_id=content_item_id,
        stage=ContentStage.FETCH,
        run_id=run_id,
        discovery_run_id=discovery_run_id,
        request_id=request_id,
        triggered_by=triggered_by,
        triggered_by_user_id=triggered_by_user_id,
    )


@shared_task(
    name="techbrief.content_pipeline.extract",
    autoretry_for=(PipelineStageError,),
    retry_backoff=60,
    retry_backoff_max=600,
    max_retries=3,
)
def run_extract(
    *,
    content_item_id: str,
    run_id: str | None = None,
    discovery_run_id: str | None = None,
    request_id: str | None = None,
    triggered_by: str = "system",
    triggered_by_user_id: str | None = None,
) -> dict:
    return _run_stage_task(
        content_item_id=content_item_id,
        stage=ContentStage.EXTRACT,
        run_id=run_id,
        discovery_run_id=discovery_run_id,
        request_id=request_id,
        triggered_by=triggered_by,
        triggered_by_user_id=triggered_by_user_id,
    )


@shared_task(
    name="techbrief.content_pipeline.transcribe",
    autoretry_for=(PipelineStageError,),
    retry_backoff=60,
    retry_backoff_max=600,
    max_retries=3,
)
def run_transcribe(
    *,
    content_item_id: str,
    run_id: str | None = None,
    discovery_run_id: str | None = None,
    request_id: str | None = None,
    triggered_by: str = "system",
    triggered_by_user_id: str | None = None,
) -> dict:
    return _run_stage_task(
        content_item_id=content_item_id,
        stage=ContentStage.TRANSCRIBE,
        run_id=run_id,
        discovery_run_id=discovery_run_id,
        request_id=request_id,
        triggered_by=triggered_by,
        triggered_by_user_id=triggered_by_user_id,
    )


@shared_task(
    name="techbrief.content_pipeline.translate",
    autoretry_for=(PipelineStageError,),
    retry_backoff=60,
    retry_backoff_max=600,
    max_retries=3,
)
def run_translate(
    *,
    content_item_id: str,
    run_id: str | None = None,
    discovery_run_id: str | None = None,
    request_id: str | None = None,
    triggered_by: str = "system",
    triggered_by_user_id: str | None = None,
) -> dict:
    return _run_stage_task(
        content_item_id=content_item_id,
        stage=ContentStage.TRANSLATE,
        run_id=run_id,
        discovery_run_id=discovery_run_id,
        request_id=request_id,
        triggered_by=triggered_by,
        triggered_by_user_id=triggered_by_user_id,
    )


@shared_task(
    name="techbrief.content_pipeline.research",
    autoretry_for=(PipelineStageError,),
    retry_backoff=60,
    retry_backoff_max=600,
    max_retries=3,
)
def run_research(
    *,
    content_item_id: str,
    run_id: str | None = None,
    discovery_run_id: str | None = None,
    request_id: str | None = None,
    triggered_by: str = "system",
    triggered_by_user_id: str | None = None,
) -> dict:
    return _run_stage_task(
        content_item_id=content_item_id,
        stage=ContentStage.RESEARCH,
        run_id=run_id,
        discovery_run_id=discovery_run_id,
        request_id=request_id,
        triggered_by=triggered_by,
        triggered_by_user_id=triggered_by_user_id,
    )


@shared_task(name="techbrief.content_pipeline.review_pending")
def run_review_pending(
    *,
    content_item_id: str,
    run_id: str | None = None,
    discovery_run_id: str | None = None,
    request_id: str | None = None,
    triggered_by: str = "system",
    triggered_by_user_id: str | None = None,
) -> dict:
    return _run_stage_task(
        content_item_id=content_item_id,
        stage=ContentStage.REVIEW_PENDING,
        run_id=run_id,
        discovery_run_id=discovery_run_id,
        request_id=request_id,
        triggered_by=triggered_by,
        triggered_by_user_id=triggered_by_user_id,
    )


@shared_task(name="techbrief.content_pipeline.publish")
def run_publish(
    *,
    content_item_id: str,
    run_id: str | None = None,
    request_id: str | None = None,
    triggered_by: str = "system",
    triggered_by_user_id: str | None = None,
) -> dict:
    content_item = ContentItem.objects.get(id=content_item_id)
    return publish_content_item(
        content_item,
        run_id=uuid.UUID(run_id) if run_id else None,
        request_id=request_id,
        triggered_by=triggered_by,
    )


@shared_task(name="techbrief.content_pipeline.notify")
def run_notify(
    *,
    content_item_id: str,
    run_id: str | None = None,
    request_id: str | None = None,
    triggered_by: str = "system",
    triggered_by_user_id: str | None = None,
) -> dict:
    content_item = ContentItem.objects.get(id=content_item_id)
    return notify_content_item(
        content_item,
        run_id=uuid.UUID(run_id) if run_id else None,
        request_id=request_id,
        triggered_by=triggered_by,
    )


def load_replay_sample(sample_name: str = "task10_publish_notify") -> dict:
    sample_path = Path(__file__).resolve().parent / "replay_samples" / f"{sample_name}.json"
    return json.loads(sample_path.read_text())


def replay_publish_notify_sample(
    *,
    sample_name: str = "task10_publish_notify",
    email_adapter: BaseEmailAdapter | None = None,
    wechat_adapter: BaseWeChatDraftAdapter | None = None,
) -> dict:
    sample = load_replay_sample(sample_name)
    source_data = sample["source"]
    content_data = sample["content_item"]
    source, _ = Source.objects.get_or_create(
        source_code=source_data["source_code"],
        defaults={
            "source_name": source_data["source_name"],
            "base_url": source_data.get("base_url"),
        },
    )
    content_item, _ = ContentItem.objects.get_or_create(
        dedupe_key=content_data["dedupe_key"],
        defaults={
            "source": source,
            "source_name_snapshot": content_data.get("source_name_snapshot") or source.source_name,
            "content_type": content_data.get("content_type", ContentType.ARTICLE),
            "ingestion_mode": content_data.get("ingestion_mode", IngestionMode.AUTO),
            "status": content_data.get("status", ContentStatus.REVIEW_PENDING),
            "current_stage": content_data.get("current_stage", ContentStage.REVIEW_PENDING),
            "title_original": content_data["title_original"],
            "title_zh": content_data.get("title_zh"),
            "summary_original": content_data.get("summary_original"),
            "summary_zh": content_data.get("summary_zh"),
            "author_or_speaker": content_data.get("author_or_speaker"),
            "source_url": content_data.get("source_url"),
            "canonical_url": content_data.get("canonical_url"),
            "content_md": content_data.get("content_md"),
            "zh_md": content_data.get("zh_md"),
            "supports_bilingual": content_data.get("supports_bilingual", True),
            "published_at_source": timezone.now(),
        },
    )
    for subscriber_data in sample.get("subscribers", []):
        Subscriber.objects.update_or_create(
            email=subscriber_data["email"].lower(),
            defaults={
                "status": subscriber_data.get("status", SubscriberStatus.ACTIVE),
                "source_page": subscriber_data.get("source_page", SubscriberSourcePage.UNKNOWN),
                "locale": subscriber_data.get("locale", "zh-CN"),
                "unsubscribe_token": subscriber_data["unsubscribe_token"],
            },
        )

    run_id = uuid.uuid4()
    publish_result = publish_content_item(
        content_item,
        run_id=run_id,
        triggered_by=TriggeredBy.SYSTEM,
    )
    notify_result = notify_content_item(
        content_item,
        email_adapter=email_adapter,
        run_id=run_id,
        triggered_by=TriggeredBy.SYSTEM,
    )
    wechat_result = create_wechat_draft(
        content_item=content_item,
        adapter=wechat_adapter,
        run_id=run_id,
        triggered_by=TriggeredBy.SYSTEM,
    )
    return {
        "content_item_id": str(content_item.id),
        "run_id": str(run_id),
        "publish": publish_result,
        "notify": notify_result,
        "wechat": wechat_result,
    }


@shared_task(name="techbrief.content_pipeline.replay_publish_notify_sample")
def replay_publish_notify_sample_task(sample_name: str = "task10_publish_notify") -> dict:
    return replay_publish_notify_sample(sample_name=sample_name)


_STAGE_TASK_FUNCS = {
    "techbrief.content_pipeline.fetch": run_fetch,
    "techbrief.content_pipeline.extract": run_extract,
    "techbrief.content_pipeline.transcribe": run_transcribe,
    "techbrief.content_pipeline.translate": run_translate,
    "techbrief.content_pipeline.research": run_research,
    "techbrief.content_pipeline.review_pending": run_review_pending,
    "techbrief.content_pipeline.publish": run_publish,
    "techbrief.content_pipeline.notify": run_notify,
}
