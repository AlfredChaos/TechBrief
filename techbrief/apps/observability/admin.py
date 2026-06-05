from __future__ import annotations

from django.contrib import admin

from .models import RunLog


@admin.register(RunLog)
class RunLogAdmin(admin.ModelAdmin):
    list_display = ("run_id", "stage", "status", "content_item", "discovery_run", "started_at")
    search_fields = ("run_id", "request_id", "error_code", "content_item__title_original")
    list_filter = ("stage", "status", "triggered_by", "retryable")
    readonly_fields = ("created_at",)
