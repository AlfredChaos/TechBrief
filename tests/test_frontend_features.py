"""Tests for frontend features: dark mode, progress bar, FAB, copy buttons, tracking pixel, GA4."""
from __future__ import annotations

import pytest
from django.core.management import call_command
from django.utils import timezone

from techbrief.apps.content_pipeline.models import ContentItem, ContentType, Source
from techbrief.apps.publishers.models import ContentPageSnapshot, PageKind
from techbrief.apps.web.theme import build_dark_mode_css_variables, build_theme_css_variables


# ── Fixtures ──────────────────────────────────────────────────────────────────


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
        title_original="Dark Mode Test Article",
        title_zh="暗黑模式测试文章",
        summary_original="Testing dark mode.",
        summary_zh="测试暗黑模式。",
        author_or_speaker="OpenAI",
        source_url="https://openai.com/test",
        canonical_url="https://openai.com/test",
        dedupe_key="c" * 64,
        published_at_source=published_at,
        published_at_web=published_at,
        supports_bilingual=True,
        web_slug="dark-mode-test",
    )
    snapshot = ContentPageSnapshot.objects.create(
        content_item=article,
        page_kind=PageKind.ARTICLE,
        slug="dark-mode-test",
        source_name_snapshot="OpenAI",
        title_original_snapshot="Dark Mode Test Article",
        title_zh_snapshot="暗黑模式测试文章",
        summary_zh_snapshot="测试暗黑模式。",
        body_original_md_snapshot="## English Heading\n\nEnglish paragraph.",
        body_zh_md_snapshot="## 中文标题\n\n中文段落。",
        author_or_speaker_snapshot="OpenAI",
        source_url_snapshot="https://openai.com/test",
        canonical_url_snapshot="https://openai.com/test",
        published_at_source_snapshot=published_at,
        supports_bilingual=True,
        disclaimer_md_snapshot="Test disclaimer.",
        is_published=True,
        published_at=published_at,
        last_synced_at=published_at,
    )
    return {"snapshot": snapshot, "article": article}


# ── Theme / dark mode ────────────────────────────────────────────────────────


def test_build_theme_css_variables_contains_colors():
    css = build_theme_css_variables()
    assert "--tb-colors-primary: #0058bc;" in css
    assert "--tb-colors-background: #fcf8fb;" in css


def test_build_dark_mode_css_variables_contains_dark_colors():
    css = build_dark_mode_css_variables()
    assert "--tb-colors-surface: #131316;" in css
    assert "--tb-colors-background: #131316;" in css
    assert "--tb-colors-primary: #adc6ff;" in css
    assert "--tb-colors-on-surface: #e4e2e4;" in css


def test_dark_mode_css_does_not_contain_typography_tokens():
    css = build_dark_mode_css_variables()
    assert "typography" not in css
    assert "spacing" not in css


# ── Template rendering ───────────────────────────────────────────────────────


@pytest.mark.django_db
def test_home_page_contains_dark_mode_css_and_progress_bar(client, seeded_site):
    response = client.get("/", HTTP_ACCEPT_LANGUAGE="zh-CN")
    body = response.content.decode()
    assert response.status_code == 200
    assert "prefers-color-scheme: dark" in body
    assert "tb-reading-progress" in body
    assert "reading-progress" in body


@pytest.mark.django_db
def test_detail_page_contains_fab_and_copy_buttons(client, seeded_site, published_content):
    response = client.get(
        "/articles/dark-mode-test?view=bilingual",
        HTTP_ACCEPT_LANGUAGE="zh-CN",
    )
    body = response.content.decode()
    assert response.status_code == 200
    # Floating subscribe button
    assert "tb-fab-subscribe" in body
    assert "id=\"fab-subscribe\"" in body
    # Copy buttons
    assert "data-copy-panel" in body
    assert "tb-copy-btn" in body


@pytest.mark.django_db
def test_detail_page_single_mode_has_copy_button(client, seeded_site, published_content):
    response = client.get(
        "/articles/dark-mode-test?view=zh",
        HTTP_ACCEPT_LANGUAGE="zh-CN",
    )
    body = response.content.decode()
    assert response.status_code == 200
    assert "data-copy-panel=\"zh\"" in body


@pytest.mark.django_db
def test_ga4_snippet_absent_when_measurement_id_empty(client, seeded_site):
    response = client.get("/", HTTP_ACCEPT_LANGUAGE="en-US")
    body = response.content.decode()
    assert "googletagmanager.com/gtag" not in body


@pytest.mark.django_db
def test_ga4_snippet_present_when_measurement_id_set(client, seeded_site, settings):
    settings.GA4_MEASUREMENT_ID = "G-TEST123"
    response = client.get("/", HTTP_ACCEPT_LANGUAGE="en-US")
    body = response.content.decode()
    assert "googletagmanager.com/gtag/js?id=G-TEST123" in body
    assert "gtag('config', 'G-TEST123')" in body


# ── Tracking pixel endpoint ──────────────────────────────────────────────────


@pytest.mark.django_db
def test_tracking_pixel_returns_gif(client):
    response = client.get("/api/public/tracking-pixel?sid=sub123&cid=art456")
    assert response.status_code == 200
    assert response["Content-Type"] == "image/gif"
    assert response.content[:6] == b"GIF89a"
    assert len(response.content) == 43
    assert "no-store" in response.get("Cache-Control", "")


@pytest.mark.django_db
def test_tracking_pixel_works_without_params(client):
    response = client.get("/api/public/tracking-pixel")
    assert response.status_code == 200
    assert response["Content-Type"] == "image/gif"


@pytest.mark.django_db
def test_tracking_pixel_rejects_post(client):
    response = client.post("/api/public/tracking-pixel")
    assert response.status_code == 405


# ── Email tracking pixel injection ──────────────────────────────────────────


@pytest.mark.django_db
def test_build_digest_email_includes_tracking_pixel(settings, published_content):
    from techbrief.apps.publishers.models import (
        EmailDigestBatch,
        EmailDigestBatchItem,
        EmailDigestStatus,
        Subscriber,
        SubscriberStatus,
    )
    from techbrief.apps.publishers.services import build_digest_email

    settings.PUBLIC_BASE_URL = "http://test.example.com"
    batch = EmailDigestBatch.objects.create(
        batch_date=timezone.localdate(),
        status=EmailDigestStatus.QUEUED,
    )
    content_item = published_content["article"]
    EmailDigestBatchItem.objects.create(batch=batch, content_item=content_item)
    subscriber = Subscriber.objects.create(
        email="pixel@example.com",
        status=SubscriberStatus.ACTIVE,
        unsubscribe_token="test-unsub-token",
    )
    subject, html, text = build_digest_email(batch=batch, subscriber=subscriber)
    assert "/api/public/tracking-pixel" in html
    assert "sid=" in html
    assert "cid=" in html
    assert "width=\"1\"" in html
    assert "height=\"1\"" in html
    assert "display:none" in html
    assert "<img" in html
