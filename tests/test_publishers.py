from __future__ import annotations

from types import SimpleNamespace

import pytest

from techbrief.apps.content_pipeline.models import ContentItem, ContentStage, ContentStatus, Source
from techbrief.apps.content_pipeline.tasks import load_replay_sample, replay_publish_notify_sample
from techbrief.apps.integrations.adapters import MockEmailAdapter, MockWeChatDraftAdapter
from techbrief.apps.observability.models import RunLog, RunLogStatus
from techbrief.apps.publishers.models import (
    ContentPageSnapshot,
    EmailDelivery,
    EmailDeliveryStatus,
    EmailDigestBatch,
    EmailDigestStatus,
    PublishChannel,
    PublishRecord,
    PublishStatus,
    Subscriber,
    SubscriberStatus,
)
from techbrief.apps.publishers.services import create_wechat_draft, publish_content_item, subscribe_email


def make_public_request(path: str, idempotency_key: str | None = None):
    headers = {"Idempotency-Key": idempotency_key} if idempotency_key else {}
    return SimpleNamespace(path=path, headers=headers, request_id="req-test-publishers")


def seed_sample_content():
    sample = load_replay_sample()
    source_data = sample["source"]
    content_data = sample["content_item"]
    source = Source.objects.create(
        source_code=source_data["source_code"],
        source_name=source_data["source_name"],
        base_url=source_data["base_url"],
    )
    content_item = ContentItem.objects.create(
        source=source,
        source_name_snapshot=content_data["source_name_snapshot"],
        content_type=content_data["content_type"],
        ingestion_mode=content_data["ingestion_mode"],
        status=content_data["status"],
        current_stage=content_data["current_stage"],
        title_original=content_data["title_original"],
        title_zh=content_data["title_zh"],
        summary_original=content_data["summary_original"],
        summary_zh=content_data["summary_zh"],
        author_or_speaker=content_data["author_or_speaker"],
        source_url=content_data["source_url"],
        canonical_url=content_data["canonical_url"],
        dedupe_key=content_data["dedupe_key"],
        content_md=content_data["content_md"],
        zh_md=content_data["zh_md"],
        supports_bilingual=content_data["supports_bilingual"],
    )
    for subscriber_data in sample["subscribers"]:
        Subscriber.objects.create(
            email=subscriber_data["email"],
            status=subscriber_data["status"],
            source_page=subscriber_data["source_page"],
            locale=subscriber_data["locale"],
            unsubscribe_token=subscriber_data["unsubscribe_token"],
        )
    return content_item


@pytest.mark.django_db
def test_subscribe_service_reactivates_unsubscribed_subscriber_idempotently():
    subscriber = Subscriber.objects.create(
        email="reader@example.com",
        status=SubscriberStatus.UNSUBSCRIBED,
        unsubscribe_token="token-reader",
    )
    request = make_public_request("/api/public/subscriptions", "idem-subscribe-1")

    payload, status = subscribe_email(
        request=request,
        payload={"email": "Reader@example.com", "source_page": "home_hero", "locale": "zh-CN"},
    )
    replay_payload, replay_status = subscribe_email(
        request=request,
        payload={"email": "reader@example.com", "source_page": "home_hero", "locale": "zh-CN"},
    )

    subscriber.refresh_from_db()
    assert status == 200
    assert replay_status == 200
    assert subscriber.status == SubscriberStatus.ACTIVE
    assert subscriber.unsubscribed_at is None
    assert payload == replay_payload
    assert Subscriber.objects.count() == 1


@pytest.mark.django_db
def test_publish_notify_and_wechat_replay_sample_use_mock_adapters(settings):
    settings.PUBLIC_BASE_URL = "http://127.0.0.1:8010"

    result = replay_publish_notify_sample(
        email_adapter=MockEmailAdapter(),
        wechat_adapter=MockWeChatDraftAdapter(),
    )

    content_item = ContentItem.objects.get(id=result["content_item_id"])
    batch = EmailDigestBatch.objects.get(id=result["notify"]["batch_id"])

    assert result["publish"]["status"] == ContentStatus.PUBLISHED
    assert batch.status == EmailDigestStatus.SENT
    assert result["wechat"]["status"] == PublishStatus.SUCCESS
    assert content_item.status == ContentStatus.PUBLISHED
    assert content_item.current_stage == ContentStage.NOTIFY
    assert ContentPageSnapshot.objects.get(content_item=content_item).is_published is True
    assert EmailDelivery.objects.filter(batch=batch, status=EmailDeliveryStatus.SENT).count() == 2
    assert PublishRecord.objects.filter(content_item=content_item, channel=PublishChannel.WEB).count() == 1
    assert RunLog.objects.filter(
        content_item=content_item,
        stage=ContentStage.PUBLISH,
        status=RunLogStatus.SUCCESS,
    ).exists()
    assert RunLog.objects.filter(
        content_item=content_item,
        stage=ContentStage.NOTIFY,
        status=RunLogStatus.SUCCESS,
    ).exists()


@pytest.mark.django_db
def test_notify_partial_failure_does_not_roll_back_web_publish(settings):
    settings.PUBLIC_BASE_URL = "http://127.0.0.1:8010"

    result = replay_publish_notify_sample(
        email_adapter=MockEmailAdapter(fail_for={"reader2@example.com"}),
        wechat_adapter=MockWeChatDraftAdapter(),
    )

    content_item = ContentItem.objects.get(id=result["content_item_id"])
    batch = EmailDigestBatch.objects.get(id=result["notify"]["batch_id"])

    assert batch.status == EmailDigestStatus.PARTIAL_FAILED
    assert result["notify"]["failed_count"] == 1
    assert content_item.status == ContentStatus.PUBLISHED
    assert ContentPageSnapshot.objects.get(content_item=content_item).is_published is True
    assert EmailDelivery.objects.filter(batch=batch, status=EmailDeliveryStatus.FAILED).count() == 1
    assert PublishRecord.objects.filter(
        content_item=content_item,
        channel=PublishChannel.WEB,
        status=PublishStatus.SUCCESS,
    ).exists()
    assert RunLog.objects.filter(
        content_item=content_item,
        stage=ContentStage.NOTIFY,
        status=RunLogStatus.FAILED,
    ).exists()


@pytest.mark.django_db
def test_wechat_draft_failure_does_not_block_web_publish(settings):
    settings.PUBLIC_BASE_URL = "http://127.0.0.1:8010"
    content_item = seed_sample_content()

    publish_result = publish_content_item(content_item)
    wechat_result = create_wechat_draft(
        content_item=content_item,
        adapter=MockWeChatDraftAdapter(fail=True),
    )

    content_item.refresh_from_db()
    web_record = PublishRecord.objects.get(
        content_item=content_item,
        channel=PublishChannel.WEB,
        status=PublishStatus.SUCCESS,
    )
    wechat_record = PublishRecord.objects.get(id=wechat_result["publish_record_id"])

    assert publish_result["status"] == ContentStatus.PUBLISHED
    assert content_item.status == ContentStatus.PUBLISHED
    assert web_record.external_id == content_item.web_slug
    assert wechat_record.status == PublishStatus.FAILED
    assert wechat_record.error_code == "MOCK_WECHAT_DRAFT_FAILED"
