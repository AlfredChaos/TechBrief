from __future__ import annotations

from django.contrib import admin

from .models import (
    ContentPageSnapshot,
    EmailDelivery,
    EmailDigestBatch,
    EmailDigestBatchItem,
    PublishRecord,
    Subscriber,
    WeChatDraftDetail,
)


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "status", "source_page", "locale", "subscribed_at")
    search_fields = ("email", "unsubscribe_token")
    list_filter = ("status", "source_page", "locale")
    readonly_fields = ("created_at", "updated_at", "subscribed_at")


@admin.register(EmailDigestBatch)
class EmailDigestBatchAdmin(admin.ModelAdmin):
    list_display = ("batch_date", "status", "provider_name", "sent_count", "failed_count")
    search_fields = ("provider_batch_id", "request_id", "error_code")
    list_filter = ("status", "provider_name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(EmailDigestBatchItem)
class EmailDigestBatchItemAdmin(admin.ModelAdmin):
    list_display = ("batch", "content_item", "sort_order", "created_at")
    search_fields = ("batch__batch_date", "content_item__title_original")
    readonly_fields = ("created_at",)


@admin.register(EmailDelivery)
class EmailDeliveryAdmin(admin.ModelAdmin):
    list_display = ("batch", "subscriber", "status", "attempt_no", "provider_message_id")
    search_fields = ("provider_message_id", "subscriber__email", "error_code")
    list_filter = ("status",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(PublishRecord)
class PublishRecordAdmin(admin.ModelAdmin):
    list_display = ("content_item", "channel", "status", "external_id", "published_at")
    search_fields = ("external_id", "request_id", "error_code", "content_item__title_original")
    list_filter = ("channel", "status", "triggered_by")
    readonly_fields = ("created_at", "updated_at")


@admin.register(WeChatDraftDetail)
class WeChatDraftDetailAdmin(admin.ModelAdmin):
    list_display = ("publish_record", "source_mode", "thumb_media_id", "retry_count", "last_retry_at")
    search_fields = ("thumb_media_id", "publish_record__external_id")
    list_filter = ("source_mode", "show_cover_pic")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ContentPageSnapshot)
class ContentPageSnapshotAdmin(admin.ModelAdmin):
    list_display = ("slug", "page_kind", "content_item", "is_published", "published_at")
    search_fields = ("slug", "title_original_snapshot", "title_zh_snapshot")
    list_filter = ("page_kind", "is_published", "supports_bilingual")
    readonly_fields = ("created_at", "updated_at")
