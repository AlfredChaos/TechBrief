"""Batch2 admin-console tests: source CRUD, content detail, manual intake/publish, workflow retry, idempotency."""
from __future__ import annotations

import uuid

import pytest
from django.urls import reverse
from django.utils import timezone

from techbrief.apps.content_pipeline.models import (
    ContentItem,
    ContentStage,
    ContentStatus,
    ContentType,
    DiscoveryRun,
    DiscoveryRunSourceStat,
    DiscoveryRunStatus,
    DiscoveryRunType,
    EndpointContentScope,
    EndpointRole,
    EndpointType,
    IngestionMode,
    Source,
    SourceEndpoint,
    TriggeredBy,
)
from techbrief.apps.core.models import User
from techbrief.apps.observability.models import RunLog, RunLogStatus
from techbrief.apps.publishers.models import (
    PublishChannel,
    PublishRecord,
    PublishStatus,
    WeChatDraftDetail,
    WeChatSourceMode,
)


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username="operator",
        email="operator@example.com",
        password="secret-123",
        display_name="Operator",
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def seeded_batch2_data(db, admin_user):
    source = Source.objects.create(
        source_code="anthropic",
        source_name="Anthropic Blog",
        base_url="https://anthropic.com",
    )
    ep = SourceEndpoint.objects.create(
        source=source,
        endpoint_type=EndpointType.RSS,
        endpoint_role=EndpointRole.PRIMARY,
        endpoint_url="https://anthropic.com/rss/blog.xml",
        content_type_scope=EndpointContentScope.ARTICLE,
        priority=100,
    )

    now = timezone.now()
    review_item = ContentItem.objects.create(
        source=source,
        source_name_snapshot="Anthropic Blog",
        content_type=ContentType.ARTICLE,
        ingestion_mode=IngestionMode.AUTO,
        status=ContentStatus.REVIEW_PENDING,
        current_stage=ContentStage.REVIEW_PENDING,
        title_original="Claude capabilities update",
        title_zh="Claude能力更新",
        summary_original="New capabilities",
        summary_zh="新能力",
        author_or_speaker="Anthropic",
        content_md="# Original content\n\nBody text",
        zh_md="# 中文内容\n\n正文",
        dedupe_key="batch2_review_001",
        published_at_source=now,
        last_processed_at=now,
        web_slug="claude-capabilities-update",
    )

    failed_item = ContentItem.objects.create(
        source=source,
        source_name_snapshot="Anthropic Blog",
        content_type=ContentType.VIDEO,
        status=ContentStatus.FAILED,
        current_stage=ContentStage.TRANSLATE,
        title_original="Video failed",
        dedupe_key="batch2_failed_001",
        published_at_source=now,
        last_error_code="TRANSLATE_TIMEOUT",
    )

    published_item = ContentItem.objects.create(
        source=source,
        source_name_snapshot="Anthropic Blog",
        content_type=ContentType.ARTICLE,
        status=ContentStatus.PUBLISHED,
        current_stage=ContentStage.NOTIFY,
        title_original="Published article",
        title_zh="已发布文章",
        dedupe_key="batch2_published_001",
        published_at_source=now,
        last_processed_at=now,
        published_at_web=now,
        web_slug="published-article",
    )

    discovery_run = DiscoveryRun.objects.create(
        run_type=DiscoveryRunType.SCHEDULED,
        status=DiscoveryRunStatus.SUCCESS,
        triggered_by=TriggeredBy.SCHEDULER,
        started_at=now,
        ended_at=now,
    )
    DiscoveryRunSourceStat.objects.create(
        discovery_run=discovery_run,
        source=source,
        endpoint=ep,
        scanned_count=10,
        new_count=3,
        updated_count=1,
        failed_count=0,
    )

    run_id = uuid.uuid4()
    RunLog.objects.create(
        run_id=run_id,
        content_item=review_item,
        discovery_run=discovery_run,
        stage=ContentStage.FETCH,
        status=RunLogStatus.SUCCESS,
        triggered_by=TriggeredBy.SCHEDULER,
        started_at=now,
        ended_at=now,
        duration_ms=800,
    )
    RunLog.objects.create(
        run_id=run_id,
        content_item=review_item,
        discovery_run=discovery_run,
        stage=ContentStage.TRANSLATE,
        status=RunLogStatus.FAILED,
        triggered_by=TriggeredBy.SCHEDULER,
        started_at=now,
        ended_at=now,
        duration_ms=5000,
        error_code="TRANSLATE_TIMEOUT",
        error_summary="Translation service timeout",
    )

    publish_record = PublishRecord.objects.create(
        content_item=published_item,
        channel=PublishChannel.WECHAT_DRAFT,
        status=PublishStatus.FAILED,
        triggered_by=TriggeredBy.ADMIN_USER,
        triggered_by_user=admin_user,
        error_code="WECHAT_API_ERROR",
        error_message="access_token expired",
    )
    WeChatDraftDetail.objects.create(
        publish_record=publish_record,
        source_mode=WeChatSourceMode.CONTENT_ITEM,
        body_source_content_item=published_item,
        show_cover_pic=True,
    )

    return {
        "source": source,
        "endpoint": ep,
        "review_item": review_item,
        "failed_item": failed_item,
        "published_item": published_item,
        "discovery_run": discovery_run,
        "run_id": str(run_id),
        "wechat_publish_record": publish_record,
    }


# ---- Source CRUD Tests ----

@pytest.mark.django_db
def test_source_list_page_renders(client, admin_user, seeded_batch2_data):
    client.force_login(admin_user)
    response = client.get(reverse("admin_console:sources"))
    assert response.status_code == 200
    assert "Source Management" in response.content.decode()
    assert "Anthropic Blog" in response.content.decode()


@pytest.mark.django_db
def test_source_list_api_returns_sources(client, admin_user, seeded_batch2_data):
    client.force_login(admin_user)
    response = client.get(reverse("admin_console:api-sources"))
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["data"]["items"]) >= 1
    source = payload["data"]["items"][0]
    assert source["source_code"] == "anthropic"
    assert len(source["endpoints"]) == 1


@pytest.mark.django_db
def test_source_detail_page_renders(client, admin_user, seeded_batch2_data):
    client.force_login(admin_user)
    source_id = seeded_batch2_data["source"].id
    response = client.get(reverse("admin_console:source-detail", args=[source_id]))
    assert response.status_code == 200
    assert "Source Detail" in response.content.decode()
    assert "Anthropic Blog" in response.content.decode()


@pytest.mark.django_db
def test_source_detail_api(client, admin_user, seeded_batch2_data):
    client.force_login(admin_user)
    source_id = seeded_batch2_data["source"].id
    response = client.get(reverse("admin_console:api-source-detail", args=[source_id]))
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["source_code"] == "anthropic"
    assert data["content_count"] == 3
    assert len(data["recent_discovery_runs"]) == 1


@pytest.mark.django_db
def test_source_create_api(client, admin_user):
    client.force_login(admin_user)
    response = client.post(
        reverse("admin_console:api-sources"),
        data={
            "source_code": "test_source",
            "source_name": "Test Source",
            "source_type": "official_site",
            "base_url": "https://test.example.com",
            "endpoints": [
                {
                    "endpoint_type": "rss",
                    "endpoint_url": "https://test.example.com/feed.xml",
                    "priority": 50,
                }
            ],
        },
        content_type="application/json",
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["source_code"] == "test_source"
    assert len(data["endpoints"]) == 1


@pytest.mark.django_db
def test_source_create_duplicate_code(client, admin_user, seeded_batch2_data):
    client.force_login(admin_user)
    response = client.post(
        reverse("admin_console:api-sources"),
        data={"source_code": "anthropic", "source_name": "Duplicate"},
        content_type="application/json",
    )
    assert response.status_code == 409


@pytest.mark.django_db
def test_source_toggle_api(client, admin_user, seeded_batch2_data):
    client.force_login(admin_user)
    source_id = seeded_batch2_data["source"].id
    response = client.post(
        reverse("admin_console:api-source-toggle", args=[source_id]),
        data={"is_enabled": False},
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["is_enabled"] is False


@pytest.mark.django_db
def test_source_delete_api(client, admin_user, seeded_batch2_data):
    client.force_login(admin_user)
    source_id = seeded_batch2_data["source"].id
    response = client.post(
        reverse("admin_console:api-source-delete", args=[source_id]),
        data={},
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "disabled"


# ---- Content Detail Tests ----

@pytest.mark.django_db
def test_content_detail_page_renders(client, admin_user, seeded_batch2_data):
    client.force_login(admin_user)
    item_id = seeded_batch2_data["review_item"].id
    response = client.get(reverse("admin_console:content-detail", args=[item_id]))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Content Detail" in content
    assert "Claude" in content
    assert "Run Logs" in content


@pytest.mark.django_db
def test_content_detail_api(client, admin_user, seeded_batch2_data):
    client.force_login(admin_user)
    item_id = seeded_batch2_data["review_item"].id
    response = client.get(reverse("admin_console:api-content-detail", args=[item_id]))
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["content"]["title_zh"] == "Claude能力更新"
    assert len(data["run_logs"]) == 2
    assert len(data["publish_records"]) == 0


# ---- Manual Intake Tests ----

@pytest.mark.django_db
def test_manual_intake_page_renders(client, admin_user, seeded_batch2_data):
    client.force_login(admin_user)
    response = client.get(reverse("admin_console:manual-intake"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Manual Intake" in content
    assert "URL Import" in content
    assert "Rich Text Entry" in content


@pytest.mark.django_db
def test_manual_intake_url_mode(client, admin_user, seeded_batch2_data):
    client.force_login(admin_user)
    response = client.post(
        reverse("admin_console:api-manual-intake"),
        data={
            "mode": "url",
            "url": "https://example.com/article/123",
            "source_id": str(seeded_batch2_data["source"].id),
        },
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "content_item_id" in data


@pytest.mark.django_db
def test_manual_intake_rich_text_mode(client, admin_user):
    client.force_login(admin_user)
    response = client.post(
        reverse("admin_console:api-manual-intake"),
        data={
            "mode": "rich_text",
            "title_original": "Manual Article",
            "title_zh": "手动文章",
            "source_name": "Manual Source",
            "body_original_md": "# Original\n\nContent",
            "body_zh_md": "# 中文\n\n内容",
        },
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == ContentStatus.REVIEW_PENDING


@pytest.mark.django_db
def test_manual_intake_invalid_mode(client, admin_user):
    client.force_login(admin_user)
    response = client.post(
        reverse("admin_console:api-manual-intake"),
        data={"mode": "invalid"},
        content_type="application/json",
    )
    assert response.status_code == 400


# ---- Manual Publish Tests ----

@pytest.mark.django_db
def test_manual_publish_page_renders(client, admin_user, seeded_batch2_data):
    client.force_login(admin_user)
    response = client.get(reverse("admin_console:manual-publish"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Manual Publish" in content
    assert "Web Publish" in content
    assert "WeChat Draft" in content
    assert "Digest Preview" in content


@pytest.mark.django_db
def test_wechat_draft_from_content(client, admin_user, seeded_batch2_data):
    client.force_login(admin_user)
    item_id = seeded_batch2_data["published_item"].id
    response = client.post(
        reverse("admin_console:api-publish-wechat"),
        data={
            "source_mode": "content_item",
            "content_item_id": str(item_id),
        },
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "publish_record_id" in data


@pytest.mark.django_db
def test_wechat_draft_manual_input(client, admin_user):
    client.force_login(admin_user)
    response = client.post(
        reverse("admin_console:api-publish-wechat"),
        data={
            "source_mode": "manual_input",
            "title": "Manual WeChat Draft",
            "author": "Test Author",
            "digest": "A test digest",
            "body_html": "<h1>Hello</h1><p>World</p>",
        },
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "publish_record_id" in data


@pytest.mark.django_db
def test_wechat_draft_retry(client, admin_user, seeded_batch2_data):
    client.force_login(admin_user)
    record_id = seeded_batch2_data["wechat_publish_record"].id
    response = client.post(
        reverse("admin_console:api-publish-wechat"),
        data={
            "action": "retry",
            "publish_record_id": str(record_id),
        },
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "status" in data


# ---- Workflow Retry Tests ----

@pytest.mark.django_db
def test_workflow_retry_api(client, admin_user, seeded_batch2_data):
    client.force_login(admin_user)
    run_id = seeded_batch2_data["run_id"]
    response = client.post(
        reverse("admin_console:api-workflow-run-retry", args=[run_id]),
        data={"stage": "translate"},
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "queued"
    assert data["stage"] == "translate"


@pytest.mark.django_db
def test_workflow_retry_invalid_stage(client, admin_user, seeded_batch2_data):
    client.force_login(admin_user)
    run_id = seeded_batch2_data["run_id"]
    response = client.post(
        reverse("admin_console:api-workflow-run-retry", args=[run_id]),
        data={"stage": "invalid_stage"},
        content_type="application/json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_content_retry_stage_api(client, admin_user, seeded_batch2_data):
    client.force_login(admin_user)
    item_id = seeded_batch2_data["failed_item"].id
    response = client.post(
        reverse("admin_console:api-content-retry-stage", args=[item_id]),
        data={"stage": "translate"},
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["stage"] == "translate"


# ---- Idempotency Tests ----

@pytest.mark.django_db
def test_idempotency_module_loads():
    """Verify idempotency module is importable and functions are available."""
    from techbrief.api.idempotency import (
        check_idempotency,
        require_csrf_and_idempotency,
        store_idempotency,
    )
    assert callable(check_idempotency)
    assert callable(store_idempotency)
    assert callable(require_csrf_and_idempotency)


@pytest.mark.django_db
def test_source_create_api_with_duplicate(client, admin_user, seeded_batch2_data):
    """Verify that creating a source with duplicate code returns 409."""
    client.force_login(admin_user)
    # First creation
    response1 = client.post(
        reverse("admin_console:api-sources"),
        data={
            "source_code": "dup_test",
            "source_name": "Dup Test",
        },
        content_type="application/json",
    )
    assert response1.status_code == 201

    # Duplicate
    response2 = client.post(
        reverse("admin_console:api-sources"),
        data={
            "source_code": "dup_test",
            "source_name": "Dup Test 2",
        },
        content_type="application/json",
    )
    assert response2.status_code == 409
    assert response2.json()["error"]["details"]["field"] == "source_code"
