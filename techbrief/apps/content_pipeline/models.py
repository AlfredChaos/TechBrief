from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from techbrief.apps.core.models import CreatedAtModel, TimeStampedModel


class SourceType(models.TextChoices):
    OFFICIAL_SITE = "official_site", "Official Site"
    VIDEO_CHANNEL = "video_channel", "Video Channel"
    MANUAL_EXTERNAL = "manual_external", "Manual External"


class EndpointType(models.TextChoices):
    RSS = "rss", "RSS"
    HTML_LIST = "html_list", "HTML List"
    SITEMAP = "sitemap", "Sitemap"
    VIDEO_CHANNEL = "video_channel", "Video Channel"


class EndpointRole(models.TextChoices):
    PRIMARY = "primary", "Primary"
    FALLBACK = "fallback", "Fallback"
    SUPPLEMENTAL = "supplemental", "Supplemental"


class EndpointContentScope(models.TextChoices):
    ARTICLE = "article", "Article"
    VIDEO = "video", "Video"
    MIXED = "mixed", "Mixed"


class DiscoveryRunType(models.TextChoices):
    SCHEDULED = "scheduled", "Scheduled"
    MANUAL = "manual", "Manual"
    REPLAY = "replay", "Replay"


class DiscoveryRunStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    RUNNING = "running", "Running"
    SUCCESS = "success", "Success"
    PARTIAL_FAILED = "partial_failed", "Partial Failed"
    FAILED = "failed", "Failed"


class TriggeredBy(models.TextChoices):
    SCHEDULER = "scheduler", "Scheduler"
    ADMIN_USER = "admin_user", "Admin User"
    SYSTEM_RETRY = "system_retry", "System Retry"
    SYSTEM = "system", "System"


class ContentType(models.TextChoices):
    ARTICLE = "article", "Article"
    VIDEO = "video", "Video"
    MANUAL = "manual", "Manual"


class IngestionMode(models.TextChoices):
    AUTO = "auto", "Auto"
    MANUAL_URL = "manual_url", "Manual URL"
    MANUAL_RICH_TEXT = "manual_rich_text", "Manual Rich Text"


class ContentStatus(models.TextChoices):
    DISCOVERED = "discovered", "Discovered"
    PROCESSING = "processing", "Processing"
    REVIEW_PENDING = "review_pending", "Review Pending"
    PUBLISHED = "published", "Published"
    FAILED = "failed", "Failed"
    ARCHIVED = "archived", "Archived"


class ContentStage(models.TextChoices):
    DISCOVER = "discover", "Discover"
    FETCH = "fetch", "Fetch"
    EXTRACT = "extract", "Extract"
    TRANSCRIBE = "transcribe", "Transcribe"
    TRANSLATE = "translate", "Translate"
    RESEARCH = "research", "Research"
    REVIEW_PENDING = "review_pending", "Review Pending"
    PUBLISH = "publish", "Publish"
    NOTIFY = "notify", "Notify"


class TextSourceStatus(models.TextChoices):
    HTML = "html", "HTML"
    SUBTITLE = "subtitle", "Subtitle"
    AUTO_SUBTITLE = "auto_subtitle", "Auto Subtitle"
    ASR = "asr", "ASR"
    MANUAL_INPUT = "manual_input", "Manual Input"
    NONE = "none", "None"


class ArtifactType(models.TextChoices):
    RAW_HTML = "raw_html", "Raw HTML"
    HTTP_RESPONSE = "http_response", "HTTP Response"
    SUBTITLE_MANUAL = "subtitle_manual", "Subtitle Manual"
    SUBTITLE_AUTO = "subtitle_auto", "Subtitle Auto"
    AUDIO = "audio", "Audio"
    TRANSCRIPT_TEXT = "transcript_text", "Transcript Text"
    TRANSCRIPT_SEGMENTS = "transcript_segments", "Transcript Segments"
    COVER_IMAGE = "cover_image", "Cover Image"
    BODY_IMAGE = "body_image", "Body Image"
    DEBUG_FILE = "debug_file", "Debug File"
    WECHAT_HTML = "wechat_html", "WeChat HTML"


class Source(TimeStampedModel):
    source_code = models.CharField(max_length=32, unique=True)
    source_name = models.CharField(max_length=128)
    source_type = models.CharField(
        max_length=32,
        choices=SourceType.choices,
        default=SourceType.OFFICIAL_SITE,
    )
    base_url = models.URLField(max_length=512, null=True, blank=True)
    default_language = models.CharField(max_length=16, default="en")
    is_enabled = models.BooleanField(default=True)
    schedule_cron_expr = models.CharField(max_length=64, default="0 2 * * *")
    notes = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "tb_source"
        indexes = [
            models.Index(fields=["is_enabled"]),
            models.Index(fields=["is_enabled", "schedule_cron_expr"]),
        ]

    def __str__(self) -> str:
        return self.source_name


class SourceEndpoint(TimeStampedModel):
    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name="endpoints")
    endpoint_type = models.CharField(max_length=32, choices=EndpointType.choices)
    endpoint_role = models.CharField(max_length=32, choices=EndpointRole.choices, default=EndpointRole.PRIMARY)
    endpoint_url = models.URLField(max_length=1024)
    content_type_scope = models.CharField(
        max_length=32,
        choices=EndpointContentScope.choices,
        default=EndpointContentScope.MIXED,
    )
    priority = models.PositiveSmallIntegerField(default=100)
    parser_config = models.JSONField(null=True, blank=True)
    last_etag = models.CharField(max_length=255, null=True, blank=True)
    last_modified_header = models.CharField(max_length=255, null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    is_enabled = models.BooleanField(default=True)

    class Meta:
        db_table = "tb_source_endpoint"
        constraints = [
            models.UniqueConstraint(fields=["source", "endpoint_url"], name="uk_tb_source_endpoint_source_url"),
        ]
        indexes = [
            models.Index(fields=["source"]),
            models.Index(fields=["is_enabled", "priority"]),
        ]

    def __str__(self) -> str:
        return self.endpoint_url


class DiscoveryRun(TimeStampedModel):
    run_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    run_type = models.CharField(max_length=32, choices=DiscoveryRunType.choices, default=DiscoveryRunType.SCHEDULED)
    status = models.CharField(max_length=32, choices=DiscoveryRunStatus.choices, default=DiscoveryRunStatus.QUEUED)
    request_id = models.CharField(max_length=64, null=True, blank=True)
    triggered_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="discovery_runs",
    )
    triggered_by = models.CharField(max_length=32, choices=TriggeredBy.choices, default=TriggeredBy.SCHEDULER)
    source_scope = models.JSONField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    discovered_count = models.PositiveIntegerField(default=0)
    enqueued_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    error_code = models.CharField(max_length=64, null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "tb_discovery_run"
        indexes = [
            models.Index(fields=["status", "started_at"]),
            models.Index(fields=["triggered_by_user"]),
        ]

    def __str__(self) -> str:
        return str(self.run_id)


class DiscoveryRunSourceStat(CreatedAtModel):
    discovery_run = models.ForeignKey(DiscoveryRun, on_delete=models.CASCADE, related_name="source_stats")
    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name="discovery_stats")
    endpoint = models.ForeignKey(
        SourceEndpoint,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="discovery_stats",
    )
    scanned_count = models.PositiveIntegerField(default=0)
    new_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    last_error_code = models.CharField(max_length=64, null=True, blank=True)
    last_error_message = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "tb_discovery_run_source_stat"
        constraints = [
            models.UniqueConstraint(
                fields=["discovery_run", "source", "endpoint"],
                condition=models.Q(endpoint__isnull=False),
                name="uk_tb_discovery_run_source_stat_scope_endpoint",
            ),
            models.UniqueConstraint(
                fields=["discovery_run", "source"],
                condition=models.Q(endpoint__isnull=True),
                name="uk_tb_discovery_run_source_stat_scope_source",
            ),
        ]
        indexes = [
            models.Index(fields=["discovery_run"]),
            models.Index(fields=["source"]),
        ]


class ContentItem(TimeStampedModel):
    source = models.ForeignKey(Source, on_delete=models.SET_NULL, null=True, blank=True, related_name="content_items")
    source_name_snapshot = models.CharField(max_length=128)
    content_type = models.CharField(max_length=32, choices=ContentType.choices)
    ingestion_mode = models.CharField(max_length=32, choices=IngestionMode.choices, default=IngestionMode.AUTO)
    status = models.CharField(max_length=32, choices=ContentStatus.choices, default=ContentStatus.DISCOVERED)
    current_stage = models.CharField(max_length=32, choices=ContentStage.choices, default=ContentStage.DISCOVER)
    title_original = models.CharField(max_length=512)
    title_zh = models.CharField(max_length=512, null=True, blank=True)
    summary_original = models.TextField(null=True, blank=True)
    summary_zh = models.TextField(null=True, blank=True)
    author_or_speaker = models.CharField(max_length=255, null=True, blank=True)
    source_url = models.URLField(max_length=1024, null=True, blank=True)
    final_url = models.URLField(max_length=1024, null=True, blank=True)
    canonical_url = models.URLField(max_length=1024, null=True, blank=True)
    source_item_id = models.CharField(max_length=255, null=True, blank=True)
    dedupe_key = models.CharField(max_length=64, unique=True)
    published_at_source = models.DateTimeField(null=True, blank=True)
    discovered_at = models.DateTimeField(auto_now_add=True)
    last_processed_at = models.DateTimeField(null=True, blank=True)
    original_language = models.CharField(max_length=16, default="en")
    text_source_status = models.CharField(max_length=32, choices=TextSourceStatus.choices, default=TextSourceStatus.NONE)
    content_ast = models.JSONField(null=True, blank=True)
    content_md = models.TextField(null=True, blank=True)
    zh_ast = models.JSONField(null=True, blank=True)
    zh_md = models.TextField(null=True, blank=True)
    research_report_md = models.TextField(null=True, blank=True)
    transcript_text = models.TextField(null=True, blank=True)
    transcript_segments_json = models.JSONField(null=True, blank=True)
    transcript_language = models.CharField(max_length=16, null=True, blank=True)
    transcription_confidence = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    metadata_json = models.JSONField(null=True, blank=True)
    supports_bilingual = models.BooleanField(default=True)
    web_slug = models.SlugField(max_length=255, unique=True, null=True, blank=True)
    published_at_web = models.DateTimeField(null=True, blank=True)
    latest_run_id = models.UUIDField(null=True, blank=True)
    last_error_code = models.CharField(max_length=64, null=True, blank=True)
    last_error_message = models.TextField(null=True, blank=True)
    last_error_stage = models.CharField(max_length=32, null=True, blank=True)
    timings_json = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "tb_content_item"
        indexes = [
            models.Index(fields=["source", "status"]),
            models.Index(
                fields=["content_type", "status", "published_at_source"],
            ),
            models.Index(fields=["canonical_url"]),
            models.Index(fields=["source_item_id"]),
            models.Index(fields=["discovered_at"]),
        ]

    def __str__(self) -> str:
        return self.title_original


class ContentArtifact(CreatedAtModel):
    content_item = models.ForeignKey(ContentItem, on_delete=models.CASCADE, related_name="artifacts")
    artifact_type = models.CharField(max_length=64, choices=ArtifactType.choices)
    storage_provider = models.CharField(max_length=32, default="tencent_cos")
    bucket_name = models.CharField(max_length=128)
    storage_key = models.CharField(max_length=1024, unique=True)
    content_type = models.CharField(max_length=128)
    file_ext = models.CharField(max_length=16, null=True, blank=True)
    language = models.CharField(max_length=16, null=True, blank=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64)
    is_primary = models.BooleanField(default=False)

    class Meta:
        db_table = "tb_content_artifact"
        indexes = [
            models.Index(fields=["content_item"]),
            models.Index(fields=["artifact_type"]),
            models.Index(fields=["content_item", "artifact_type"]),
        ]

    def __str__(self) -> str:
        return self.storage_key
