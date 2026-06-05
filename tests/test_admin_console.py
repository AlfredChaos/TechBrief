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
    DiscoveryRunStatus,
    DiscoveryRunType,
    Source,
    TriggeredBy,
)
from techbrief.apps.core.models import User
from techbrief.apps.observability.models import RunLog, RunLogStatus
from techbrief.apps.publishers.models import Subscriber, SubscriberSourcePage, SubscriberStatus


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
def seeded_admin_console_data(db, admin_user):
    source = Source.objects.create(
        source_code="openai",
        source_name="OpenAI",
        base_url="https://openai.com",
    )

    now = timezone.now()
    review_content = ContentItem.objects.create(
        source=source,
        source_name_snapshot="OpenAI",
        content_type=ContentType.ARTICLE,
        status=ContentStatus.REVIEW_PENDING,
        current_stage=ContentStage.REVIEW_PENDING,
        title_original="Reasoning models need better interfaces",
        title_zh="推理模型需要更好的界面",
        dedupe_key="a" * 64,
        published_at_source=now,
        last_processed_at=now,
        web_slug="reasoning-models-better-interfaces",
    )
    failed_content = ContentItem.objects.create(
        source=source,
        source_name_snapshot="OpenAI",
        content_type=ContentType.VIDEO,
        status=ContentStatus.FAILED,
        current_stage=ContentStage.TRANSLATE,
        title_original="Video pipeline failed",
        dedupe_key="b" * 64,
        published_at_source=now,
    )

    Subscriber.objects.create(
        email="reader@example.com",
        status=SubscriberStatus.ACTIVE,
        source_page=SubscriberSourcePage.HOME_HERO,
        unsubscribe_token="token-active",
        last_sent_at=now,
    )
    Subscriber.objects.create(
        email="paused@example.com",
        status=SubscriberStatus.UNSUBSCRIBED,
        source_page=SubscriberSourcePage.NAV_MODAL,
        unsubscribe_token="token-unsubscribed",
        unsubscribed_at=now,
    )

    discovery_run = DiscoveryRun.objects.create(
        run_type=DiscoveryRunType.MANUAL,
        status=DiscoveryRunStatus.SUCCESS,
        triggered_by=TriggeredBy.ADMIN_USER,
        triggered_by_user=admin_user,
        started_at=now,
        ended_at=now,
    )

    workflow_run_id = uuid.uuid4()
    RunLog.objects.create(
        run_id=workflow_run_id,
        content_item=review_content,
        discovery_run=discovery_run,
        stage=ContentStage.FETCH,
        status=RunLogStatus.SUCCESS,
        triggered_by=TriggeredBy.ADMIN_USER,
        triggered_by_user=admin_user,
        started_at=now,
        ended_at=now,
        duration_ms=1200,
    )
    RunLog.objects.create(
        run_id=workflow_run_id,
        content_item=review_content,
        discovery_run=discovery_run,
        stage=ContentStage.TRANSLATE,
        status=RunLogStatus.FAILED,
        triggered_by=TriggeredBy.ADMIN_USER,
        triggered_by_user=admin_user,
        started_at=now,
        ended_at=now,
        duration_ms=3200,
        error_code="TRANSLATE_TIMEOUT",
    )

    return {
        "review_content": review_content,
        "failed_content": failed_content,
        "workflow_run_id": str(workflow_run_id),
    }


@pytest.mark.django_db
def test_admin_console_pages_require_authentication(client):
    response = client.get(reverse("admin_console:dashboard"))

    assert response.status_code == 302
    assert reverse("wagtailadmin_login") in response.url


@pytest.mark.django_db
def test_authenticated_admin_console_pages_render(client, admin_user, seeded_admin_console_data):
    client.force_login(admin_user)

    dashboard_response = client.get(reverse("admin_console:dashboard"))
    content_response = client.get(reverse("admin_console:content"))
    subscribers_response = client.get(reverse("admin_console:subscribers"))
    workflow_response = client.get(reverse("admin_console:workflow"))

    assert dashboard_response.status_code == 200
    assert "Admin Dashboard" in dashboard_response.content.decode()
    assert "--tb-colors-primary:" in dashboard_response.content.decode()
    assert content_response.status_code == 200
    assert "Content Queue" in content_response.content.decode()
    assert subscribers_response.status_code == 200
    assert "Subscribers" in subscribers_response.content.decode()
    assert workflow_response.status_code == 200
    assert "Workflow Monitor" in workflow_response.content.decode()


@pytest.mark.django_db
def test_dashboard_api_returns_metrics_and_recent_activity(client, admin_user, seeded_admin_console_data):
    client.force_login(admin_user)

    response = client.get(reverse("admin_console:api-dashboard"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["metrics"]["subscriber_total"] == 2
    assert payload["data"]["metrics"]["review_pending_count"] == 1
    assert payload["data"]["system_status"]["database"] == "online"
    assert payload["data"]["recent_activities"]


@pytest.mark.django_db
def test_content_api_supports_filters_and_actions(client, admin_user, seeded_admin_console_data):
    client.force_login(admin_user)

    response = client.get(
        reverse("admin_console:api-content"),
        {
            "status": ContentStatus.REVIEW_PENDING,
            "q": "界面",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["pagination"]["total"] == 1
    item = payload["data"]["items"][0]
    assert item["title_zh"] == "推理模型需要更好的界面"
    assert "publish_web" in item["available_actions"]


@pytest.mark.django_db
def test_subscriber_api_filters_by_status(client, admin_user, seeded_admin_console_data):
    client.force_login(admin_user)

    response = client.get(
        reverse("admin_console:api-subscribers"),
        {
            "status": SubscriberStatus.UNSUBSCRIBED,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["pagination"]["total"] == 1
    assert payload["data"]["items"][0]["email"] == "paused@example.com"


@pytest.mark.django_db
def test_workflow_api_aggregates_run_logs(client, admin_user, seeded_admin_console_data):
    client.force_login(admin_user)

    response = client.get(
        reverse("admin_console:api-workflow"),
        {
            "status": RunLogStatus.FAILED,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["summary"]["total_runs"] == 1
    assert payload["data"]["summary"]["failed_runs"] == 1
    assert payload["data"]["items"][0]["run_id"] == seeded_admin_console_data["workflow_run_id"]
    assert payload["data"]["items"][0]["error_code"] == "TRANSLATE_TIMEOUT"
