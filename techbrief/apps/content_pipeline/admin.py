from __future__ import annotations

from django.contrib import admin

from .models import (
    ContentArtifact,
    ContentItem,
    DiscoveryRun,
    DiscoveryRunSourceStat,
    Source,
    SourceEndpoint,
)


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ("source_code", "source_name", "source_type", "is_enabled", "schedule_cron_expr")
    search_fields = ("source_code", "source_name")
    list_filter = ("source_type", "is_enabled")
    readonly_fields = ("created_at", "updated_at")


@admin.register(SourceEndpoint)
class SourceEndpointAdmin(admin.ModelAdmin):
    list_display = ("source", "endpoint_type", "endpoint_role", "priority", "is_enabled")
    search_fields = ("endpoint_url", "source__source_name", "source__source_code")
    list_filter = ("endpoint_type", "endpoint_role", "is_enabled")
    readonly_fields = ("created_at", "updated_at")


@admin.register(DiscoveryRun)
class DiscoveryRunAdmin(admin.ModelAdmin):
    list_display = ("run_id", "run_type", "status", "triggered_by", "started_at", "ended_at")
    search_fields = ("run_id", "request_id", "error_code")
    list_filter = ("run_type", "status", "triggered_by")
    readonly_fields = ("created_at", "updated_at")


@admin.register(DiscoveryRunSourceStat)
class DiscoveryRunSourceStatAdmin(admin.ModelAdmin):
    list_display = ("discovery_run", "source", "endpoint", "scanned_count", "new_count", "failed_count")
    search_fields = ("discovery_run__run_id", "source__source_code", "endpoint__endpoint_url")
    readonly_fields = ("created_at",)


@admin.register(ContentItem)
class ContentItemAdmin(admin.ModelAdmin):
    list_display = (
        "title_original",
        "content_type",
        "status",
        "current_stage",
        "source_name_snapshot",
        "published_at_source",
    )
    search_fields = ("title_original", "title_zh", "dedupe_key", "web_slug", "canonical_url")
    list_filter = ("content_type", "status", "current_stage", "supports_bilingual")
    readonly_fields = ("created_at", "updated_at", "discovered_at")


@admin.register(ContentArtifact)
class ContentArtifactAdmin(admin.ModelAdmin):
    list_display = ("content_item", "artifact_type", "storage_provider", "bucket_name", "is_primary")
    search_fields = ("storage_key", "sha256", "content_item__title_original")
    list_filter = ("artifact_type", "storage_provider", "is_primary")
    readonly_fields = ("created_at",)
