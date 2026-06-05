from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command


@pytest.mark.django_db
def test_bootstrap_initial_admin_creates_or_updates_platform_admin(settings):
    settings.INITIAL_ADMIN_USERNAME = "admin"
    settings.INITIAL_ADMIN_EMAIL = "ADMIN@EXAMPLE.COM"
    settings.INITIAL_ADMIN_PASSWORD = "secret-123"

    call_command("bootstrap_initial_admin")

    user = get_user_model().objects.get(username="admin")
    assert user.email == "admin@example.com"
    assert user.display_name == "admin"
    assert user.is_staff is True
    assert user.is_superuser is True
    assert user.is_platform_admin is True
    assert user.check_password("secret-123")

    settings.INITIAL_ADMIN_EMAIL = "owner@example.com"
    settings.INITIAL_ADMIN_PASSWORD = "secret-456"
    call_command("bootstrap_initial_admin")

    user.refresh_from_db()
    assert user.email == "owner@example.com"
    assert user.check_password("secret-456")
