from __future__ import annotations

from django.conf import settings
from django.db import models

from techbrief.apps.content_pipeline.models import ContentArtifact, ContentItem, TriggeredBy
from techbrief.apps.core.models import CreatedAtModel, TimeStampedModel


class SubscriberStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    UNSUBSCRIBED = "unsubscribed", "Unsubscribed"
    BOUNCED = "bounced", "Bounced"
    COMPLAINED = "complained", "Complained"


class SubscriberSourcePage(models.TextChoices):
    HOME_HERO = "home_hero", "Home Hero"
    NAV_MODAL = "nav_modal", "Nav Modal"
    SUBSCRIPTION_MODAL = "subscription_modal", "Subscription Modal"
    ARTICLE_FLOATING_CTA = "article_floating_cta", "Article Floating CTA"
    UNKNOWN = "unknown", "Unknown"


class EmailDigestStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    SENDING = "sending", "Sending"
    SENT = "sent", "Sent"
    PARTIAL_FAILED = "partial_failed", "Partial Failed"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


class EmailDeliveryStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    SENT = "sent", "Sent"
    DELIVERED = "delivered", "Delivered"
    BOUNCED = "bounced", "Bounced"
    FAILED = "failed", "Failed"
    UNSUBSCRIBED = "unsubscribed", "Unsubscribed"


class PublishChannel(models.TextChoices):
    WEB = "web", "Web"
    WECHAT_DRAFT = "wechat_draft", "WeChat Draft"
    EMAIL_DIGEST = "email_digest", "Email Digest"


class PublishStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


class WeChatSourceMode(models.TextChoices):
    CONTENT_ITEM = "content_item", "Content Item"
    MANUAL_INPUT = "manual_input", "Manual Input"


class PageKind(models.TextChoices):
    ARTICLE = "article", "Article"
    VIDEO = "video", "Video"


class Subscriber(TimeStampedModel):
    email = models.EmailField(max_length=320, unique=True)
    status = models.CharField(max_length=32, choices=SubscriberStatus.choices, default=SubscriberStatus.ACTIVE)
    source_page = models.CharField(max_length=64, choices=SubscriberSourcePage.choices, default=SubscriberSourcePage.UNKNOWN)
    locale = models.CharField(max_length=16, default="zh-CN")
    unsubscribe_token = models.CharField(max_length=128, unique=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    last_bounced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "tb_subscriber"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["subscribed_at"]),
        ]

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.email


class EmailDigestBatch(TimeStampedModel):
    batch_date = models.DateField(unique=True)
    status = models.CharField(max_length=32, choices=EmailDigestStatus.choices, default=EmailDigestStatus.QUEUED)
    triggered_by = models.CharField(max_length=32, choices=TriggeredBy.choices, default=TriggeredBy.SCHEDULER)
    triggered_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="email_digest_batches",
    )
    request_id = models.CharField(max_length=64, null=True, blank=True)
    total_content_count = models.PositiveIntegerField(default=0)
    total_recipient_count = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    provider_name = models.CharField(max_length=32, default="resend")
    provider_batch_id = models.CharField(max_length=255, null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_code = models.CharField(max_length=64, null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "tb_email_digest_batch"
        indexes = [
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return str(self.batch_date)


class EmailDigestBatchItem(CreatedAtModel):
    batch = models.ForeignKey(EmailDigestBatch, on_delete=models.CASCADE, related_name="items")
    content_item = models.ForeignKey(ContentItem, on_delete=models.CASCADE, related_name="digest_items")
    sort_order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        db_table = "tb_email_digest_batch_item"
        constraints = [
            models.UniqueConstraint(fields=["batch", "content_item"], name="uk_tb_email_digest_batch_item_unique"),
        ]
        indexes = [
            models.Index(fields=["batch"]),
            models.Index(fields=["content_item"]),
        ]


class EmailDelivery(TimeStampedModel):
    batch = models.ForeignKey(EmailDigestBatch, on_delete=models.CASCADE, related_name="deliveries")
    subscriber = models.ForeignKey(Subscriber, on_delete=models.CASCADE, related_name="deliveries")
    status = models.CharField(max_length=32, choices=EmailDeliveryStatus.choices, default=EmailDeliveryStatus.QUEUED)
    provider_message_id = models.CharField(max_length=255, null=True, blank=True)
    attempt_no = models.PositiveSmallIntegerField(default=1)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    error_code = models.CharField(max_length=64, null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "tb_email_delivery"
        constraints = [
            models.UniqueConstraint(fields=["batch", "subscriber"], name="uk_tb_email_delivery_batch_subscriber"),
        ]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["subscriber"]),
            models.Index(fields=["provider_message_id"]),
        ]


class PublishRecord(TimeStampedModel):
    content_item = models.ForeignKey(ContentItem, on_delete=models.CASCADE, related_name="publish_records")
    channel = models.CharField(max_length=32, choices=PublishChannel.choices)
    status = models.CharField(max_length=32, choices=PublishStatus.choices, default=PublishStatus.QUEUED)
    request_id = models.CharField(max_length=64, null=True, blank=True)
    run_id = models.UUIDField(null=True, blank=True)
    triggered_by = models.CharField(max_length=32, choices=TriggeredBy.choices, default=TriggeredBy.SYSTEM)
    triggered_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="publish_records",
    )
    email_digest_batch = models.ForeignKey(
        EmailDigestBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="publish_records",
    )
    external_id = models.CharField(max_length=255, null=True, blank=True)
    payload_snapshot = models.JSONField(null=True, blank=True)
    response_snapshot = models.JSONField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    error_code = models.CharField(max_length=64, null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "tb_publish_record"
        indexes = [
            models.Index(fields=["content_item"]),
            models.Index(fields=["channel", "status"]),
            models.Index(fields=["external_id"]),
            models.Index(fields=["email_digest_batch"]),
        ]


class WeChatDraftDetail(TimeStampedModel):
    publish_record = models.OneToOneField(PublishRecord, on_delete=models.CASCADE, related_name="wechat_detail")
    source_mode = models.CharField(max_length=32, choices=WeChatSourceMode.choices)
    manual_title = models.CharField(max_length=512, null=True, blank=True)
    manual_author = models.CharField(max_length=255, null=True, blank=True)
    manual_digest = models.TextField(null=True, blank=True)
    body_source_content_item = models.ForeignKey(
        ContentItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wechat_body_usages",
    )
    thumb_media_id = models.CharField(max_length=255, null=True, blank=True)
    wechat_html_artifact = models.ForeignKey(
        ContentArtifact,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wechat_draft_details",
    )
    show_cover_pic = models.BooleanField(default=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    last_retry_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "tb_wechat_draft_detail"
        indexes = [
            models.Index(fields=["body_source_content_item"]),
        ]


class ContentPageSnapshot(TimeStampedModel):
    content_item = models.OneToOneField(ContentItem, on_delete=models.CASCADE, related_name="page_snapshot")
    page_kind = models.CharField(max_length=32, choices=PageKind.choices)
    slug = models.SlugField(max_length=255, unique=True)
    source_name_snapshot = models.CharField(max_length=128)
    title_original_snapshot = models.CharField(max_length=512)
    title_zh_snapshot = models.CharField(max_length=512)
    summary_zh_snapshot = models.TextField(null=True, blank=True)
    body_original_md_snapshot = models.TextField(null=True, blank=True)
    body_zh_md_snapshot = models.TextField()
    author_or_speaker_snapshot = models.CharField(max_length=255, null=True, blank=True)
    source_url_snapshot = models.URLField(max_length=1024)
    canonical_url_snapshot = models.URLField(max_length=1024, null=True, blank=True)
    published_at_source_snapshot = models.DateTimeField(null=True, blank=True)
    supports_bilingual = models.BooleanField(default=True)
    disclaimer_md_snapshot = models.TextField()
    seo_title = models.CharField(max_length=255, null=True, blank=True)
    seo_description = models.CharField(max_length=512, null=True, blank=True)
    cover_artifact = models.ForeignKey(
        ContentArtifact,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="page_snapshots",
    )
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "tb_content_page_snapshot"
        indexes = [
            models.Index(fields=["page_kind", "is_published"]),
        ]

    def __str__(self) -> str:
        return self.slug
