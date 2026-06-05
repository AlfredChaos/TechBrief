from __future__ import annotations

import json

import pytest
from django.core.management import call_command
from wagtail.models import Site

from techbrief.apps.web.management.commands.load_site_seed import DEFAULT_SEED_PATH
from techbrief.apps.web.models import HomePage, ListingPage, StaticPage


@pytest.mark.django_db
def test_load_site_seed_creates_default_page_tree(settings):
    settings.PUBLIC_BASE_URL = "http://127.0.0.1:8010"

    call_command("load_site_seed")

    home_page = HomePage.objects.get()
    assert home_page.slug == "techbrief-home"
    assert home_page.title_zh == "TechBrief"
    assert home_page.live is True

    listing_pages = {page.page_code: page for page in ListingPage.objects.all()}
    assert set(listing_pages) == {"articles", "archive"}
    assert listing_pages["articles"].page_size == 20

    static_pages = {page.page_code: page for page in StaticPage.objects.all()}
    assert set(static_pages) == {"about", "privacy", "terms"}
    assert "TechBrief" in static_pages["about"].body_md_en

    site = Site.objects.get(is_default_site=True)
    assert site.root_page_id == home_page.id
    assert isinstance(site.root_page.specific, HomePage)
    assert site.hostname == "127.0.0.1"
    assert site.port == 8010


@pytest.mark.django_db
def test_load_site_seed_is_idempotent_and_updates_existing_pages(tmp_path):
    payload = json.loads(DEFAULT_SEED_PATH.read_text())
    payload["home_page"]["hero_title_en"] = "Updated Hero Title"
    payload["static_pages"][0]["seo_title_en"] = "Updated About SEO"

    seed_path = tmp_path / "base_pages.json"
    seed_path.write_text(json.dumps(payload))

    call_command("load_site_seed", file=str(seed_path))
    call_command("load_site_seed", file=str(seed_path))

    assert HomePage.objects.count() == 1
    assert ListingPage.objects.count() == 2
    assert StaticPage.objects.count() == 3
    assert HomePage.objects.get().hero_title_en == "Updated Hero Title"
    assert StaticPage.objects.get(page_code="about").seo_title_en == "Updated About SEO"
