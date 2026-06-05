from __future__ import annotations

import json

import pytest
from django.core.management import call_command
from django.utils import timezone

from techbrief.apps.content_pipeline.models import ContentItem, ContentType, Source
from techbrief.apps.publishers.models import ContentPageSnapshot, PageKind, Subscriber, SubscriberStatus


@pytest.fixture
def seeded_site(settings):
    settings.PUBLIC_BASE_URL = "http://127.0.0.1:8010"
    call_command("load_site_seed")


@pytest.fixture
def published_content(db):
    source = Source.objects.create(
        source_code="openai",
        source_name="OpenAI",
        base_url="https://openai.com",
    )
    published_at = timezone.now()

    article = ContentItem.objects.create(
        source=source,
        source_name_snapshot="OpenAI",
        content_type=ContentType.ARTICLE,
        status="published",
        current_stage="publish",
        title_original="OpenAI Reasoning Models",
        title_zh="OpenAI 推理模型",
        summary_original="Reasoning models reshape problem solving.",
        summary_zh="推理模型正在重塑复杂问题求解流程。",
        author_or_speaker="OpenAI",
        source_url="https://openai.com/research/reasoning",
        canonical_url="https://openai.com/research/reasoning",
        dedupe_key="a" * 64,
        published_at_source=published_at,
        published_at_web=published_at,
        supports_bilingual=True,
        web_slug="openai-reasoning-models",
    )
    video = ContentItem.objects.create(
        source=source,
        source_name_snapshot="OpenAI",
        content_type=ContentType.VIDEO,
        status="published",
        current_stage="publish",
        title_original="Realtime Multimodal Demo",
        title_zh="实时多模态演示",
        summary_original="Realtime voice and vision demo.",
        summary_zh="实时语音与视觉演示。",
        author_or_speaker="OpenAI",
        source_url="https://openai.com/demo/realtime",
        canonical_url="https://openai.com/demo/realtime",
        dedupe_key="b" * 64,
        published_at_source=published_at,
        published_at_web=published_at,
        supports_bilingual=False,
        web_slug="realtime-multimodal-demo",
    )

    article_snapshot = ContentPageSnapshot.objects.create(
        content_item=article,
        page_kind=PageKind.ARTICLE,
        slug="openai-reasoning-models",
        source_name_snapshot="OpenAI",
        title_original_snapshot="OpenAI Reasoning Models",
        title_zh_snapshot="OpenAI 推理模型",
        summary_zh_snapshot="推理模型正在重塑复杂问题求解流程。",
        body_original_md_snapshot="## How it works\n\nReasoning models take more deliberate steps.",
        body_zh_md_snapshot="## 工作原理\n\n推理模型会进行更完整的中间思考。",
        author_or_speaker_snapshot="OpenAI",
        source_url_snapshot="https://openai.com/research/reasoning",
        canonical_url_snapshot="https://openai.com/research/reasoning",
        published_at_source_snapshot=published_at,
        supports_bilingual=True,
        disclaimer_md_snapshot="This is a translated editorial briefing.",
        is_published=True,
        published_at=published_at,
        last_synced_at=published_at,
    )
    video_snapshot = ContentPageSnapshot.objects.create(
        content_item=video,
        page_kind=PageKind.VIDEO,
        slug="realtime-multimodal-demo",
        source_name_snapshot="OpenAI",
        title_original_snapshot="Realtime Multimodal Demo",
        title_zh_snapshot="实时多模态演示",
        summary_zh_snapshot="实时语音与视觉演示。",
        body_original_md_snapshot="## Demo\n\nLive voice and image interaction.",
        body_zh_md_snapshot="## 演示\n\n展示实时语音与图像交互。",
        author_or_speaker_snapshot="OpenAI",
        source_url_snapshot="https://openai.com/demo/realtime",
        canonical_url_snapshot="https://openai.com/demo/realtime",
        published_at_source_snapshot=published_at,
        supports_bilingual=False,
        disclaimer_md_snapshot="This is a translated editorial briefing.",
        is_published=True,
        published_at=published_at,
        last_synced_at=published_at,
    )
    return {
        "source": source,
        "article": article,
        "video": video,
        "article_snapshot": article_snapshot,
        "video_snapshot": video_snapshot,
    }


@pytest.mark.django_db
def test_public_ssr_pages_render_with_seed_and_content(client, seeded_site, published_content):
    response = client.get("/", HTTP_ACCEPT_LANGUAGE="zh-CN")
    assert response.status_code == 200
    assert "Liquid Narrative" in response.content.decode()
    assert "OpenAI 推理模型" in response.content.decode()

    response = client.get("/articles", HTTP_ACCEPT_LANGUAGE="zh-CN")
    assert response.status_code == 200
    assert "OpenAI 推理模型" in response.content.decode()

    response = client.get("/articles/openai-reasoning-models?view=bilingual", HTTP_ACCEPT_LANGUAGE="zh-CN")
    assert response.status_code == 200
    body = response.content.decode()
    assert "工作原理" in body
    assert "How it works" in body

    response = client.get("/about", HTTP_ACCEPT_LANGUAGE="zh-CN")
    assert response.status_code == 200
    assert "TechBrief" in response.content.decode()


@pytest.mark.django_db
def test_public_content_items_api_returns_filtered_items(client, seeded_site, published_content):
    response = client.get(
        "/api/public/content-items?source=openai&content_type=article",
        HTTP_ACCEPT_LANGUAGE="zh-CN",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["pagination"]["total"] == 1
    assert payload["data"]["items"][0]["slug"] == "openai-reasoning-models"
    assert payload["data"]["items"][0]["title"] == "OpenAI 推理模型"


@pytest.mark.django_db
def test_public_content_item_detail_api_returns_bilingual_payload(client, seeded_site, published_content):
    response = client.get(
        "/api/public/content-items/openai-reasoning-models?view=bilingual",
        HTTP_ACCEPT_LANGUAGE="en-US",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["view_mode"] == "bilingual"
    assert payload["data"]["title_original"] == "OpenAI Reasoning Models"
    assert payload["data"]["content_blocks_zh"][0]["text"] == "工作原理"
    assert payload["data"]["content_blocks_original"][0]["text"] == "How it works"


@pytest.mark.django_db
def test_public_subscription_and_unsubscribe_endpoints_are_available(client, seeded_site):
    response = client.post(
        "/api/public/subscriptions",
        data=json.dumps(
            {
                "email": "Reader@Example.com",
                "source_page": "home_hero",
                "locale": "zh-CN",
            }
        ),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="idem-public-1",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["status"] == "active"
    subscriber = Subscriber.objects.get(email="reader@example.com")
    assert subscriber.locale == "zh-CN"

    repeat = client.post(
        "/api/public/subscriptions",
        data=json.dumps(
            {
                "email": "reader@example.com",
                "source_page": "home_hero",
                "locale": "zh-CN",
            }
        ),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="idem-public-1",
    )
    assert repeat.status_code == 200
    assert Subscriber.objects.count() == 1

    unsubscribe = client.post(
        "/api/public/subscriptions/unsubscribe",
        data=json.dumps({"token": subscriber.unsubscribe_token}),
        content_type="application/json",
    )
    assert unsubscribe.status_code == 200
    subscriber.refresh_from_db()
    assert subscriber.status == SubscriberStatus.UNSUBSCRIBED

    page = client.get(f"/unsubscribe/{subscriber.unsubscribe_token}", HTTP_ACCEPT_LANGUAGE="zh-CN")
    assert page.status_code == 200
    assert "退订已生效" in page.content.decode()
