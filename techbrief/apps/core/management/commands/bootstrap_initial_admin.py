from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create or update the initial Django superuser from environment variables."

    def handle(self, *args, **options):
        username = getattr(settings, "INITIAL_ADMIN_USERNAME", "")
        email = getattr(settings, "INITIAL_ADMIN_EMAIL", "")
        password = getattr(settings, "INITIAL_ADMIN_PASSWORD", "")
        if not username or not email or not password:
            raise CommandError("INITIAL_ADMIN_USERNAME, INITIAL_ADMIN_EMAIL, and INITIAL_ADMIN_PASSWORD are required")

        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(username=username, defaults={"email": email})
        user.email = email
        if not user.display_name or user.display_name == "Admin":
            user.display_name = username
        user.is_staff = True
        user.is_superuser = True
        user.is_platform_admin = True
        user.is_active = True
        user.set_password(password)
        user.save()
        action = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"Initial admin {action}: {username}"))
