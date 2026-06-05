from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from wagtail.models import Page, Site

from techbrief.apps.web.models import HomePage, ListingPage, StaticPage

DEFAULT_SEED_PATH = Path(__file__).resolve().parents[2] / "seed_data" / "base_pages.json"


class Command(BaseCommand):
    help = "Load or update the default Wagtail base pages from a seed file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default=str(DEFAULT_SEED_PATH),
            help="Path to a JSON file containing the base page seed payload.",
        )

    def handle(self, *args, **options):
        seed_path = Path(options["file"]).expanduser().resolve()
        if not seed_path.exists():
            raise CommandError(f"Seed file does not exist: {seed_path}")

        try:
            payload = json.loads(seed_path.read_text())
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON in seed file: {exc}") from exc

        with transaction.atomic():
            root_page = Page.get_first_root_node()
            home_page = self._upsert_home_page(root_page, payload["home_page"])
            self._upsert_collection(home_page, ListingPage, payload["listing_pages"], "page_code")
            self._upsert_collection(home_page, StaticPage, payload["static_pages"], "page_code")
            site = self._ensure_default_site(home_page)

        self.stdout.write(
            self.style.SUCCESS(
                f"Loaded site seed for '{site.hostname}' with root page '{home_page.title}'."
            )
        )

    def _upsert_home_page(self, root_page: Page, data: dict) -> HomePage:
        existing_home = root_page.get_children().type(HomePage).specific().first()
        if existing_home is not None:
            self._assign_fields(existing_home, data)
            existing_home.save()
            if getattr(existing_home, "is_published", True):
                existing_home.save_revision().publish()
            else:
                existing_home.save_revision()
            self.stdout.write(f"Updated HomePage: {existing_home.slug}")
            return existing_home

        return self._upsert_child_page(
            parent=root_page,
            model=HomePage,
            lookup_value=data["slug"],
            lookup_field="slug",
            data=data,
        )

    def _upsert_collection(self, parent: Page, model, items: list[dict], lookup_field: str) -> None:
        for item in items:
            self._upsert_child_page(
                parent=parent,
                model=model,
                lookup_value=item[lookup_field],
                lookup_field=lookup_field,
                data=item,
            )

    def _upsert_child_page(self, parent: Page, model, lookup_value: str, lookup_field: str, data: dict):
        page = self._find_child(parent, model, lookup_field, lookup_value)
        if page is None:
            page = model()
            self._assign_fields(page, data)
            parent.add_child(instance=page)
            action = "Created"
        else:
            self._assign_fields(page, data)
            page.save()
            action = "Updated"

        if getattr(page, "is_published", True):
            page.save_revision().publish()
        else:
            page.save_revision()

        self.stdout.write(f"{action} {model.__name__}: {page.slug}")
        return page

    def _find_child(self, parent: Page, model, lookup_field: str, lookup_value: str):
        children = parent.get_children().type(model).specific()
        for child in children:
            value = getattr(child, lookup_field if lookup_field != "slug" else "slug")
            if value == lookup_value:
                return child
        return None

    def _assign_fields(self, page: Page, data: dict) -> None:
        for field, value in data.items():
            setattr(page, field, value)

    def _ensure_default_site(self, root_page: HomePage) -> Site:
        parsed = urlparse(settings.PUBLIC_BASE_URL)
        hostname = parsed.hostname or "localhost"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)

        site = Site.objects.filter(is_default_site=True).first()
        if site is None:
            site = Site(
                hostname=hostname,
                port=port,
                site_name=settings.WAGTAIL_SITE_NAME,
                root_page=root_page,
                is_default_site=True,
            )
        else:
            site.hostname = hostname
            site.port = port
            site.site_name = settings.WAGTAIL_SITE_NAME
            site.root_page = root_page
            site.is_default_site = True

        site.save()
        return site
