from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import IdempotencyKey, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        "username",
        "email",
        "display_name",
        "is_active",
        "is_staff",
        "is_platform_admin",
    )
    search_fields = ("username", "email", "display_name")
    readonly_fields = ("last_login", "date_joined", "created_at", "updated_at")
    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            "TechBrief",
            {
                "fields": ("display_name", "is_platform_admin", "created_at", "updated_at"),
            },
        ),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        (
            "TechBrief",
            {
                "fields": ("email", "display_name", "is_platform_admin"),
            },
        ),
    )


@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = ("action", "operator_scope", "key", "status", "response_status", "expires_at")
    search_fields = ("action", "operator_scope", "key", "request_id")
    list_filter = ("action", "status")
    readonly_fields = ("created_at", "updated_at")
