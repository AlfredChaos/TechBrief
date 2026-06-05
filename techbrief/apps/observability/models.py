from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from techbrief.apps.content_pipeline.models import ContentItem, ContentStage, DiscoveryRun, TriggeredBy
from techbrief.apps.core.models import CreatedAtModel


class RunLogStatus(models.TextChoices):
    RUNNING = "running", "Running"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"


class RunLog(CreatedAtModel):
    run_id = models.UUIDField(default=uuid.uuid4, editable=False)
    request_id = models.CharField(max_length=64, null=True, blank=True)
    content_item = models.ForeignKey(ContentItem, on_delete=models.CASCADE, null=True, blank=True, related_name="run_logs")
    discovery_run = models.ForeignKey(DiscoveryRun, on_delete=models.CASCADE, null=True, blank=True, related_name="run_logs")
    stage = models.CharField(max_length=32, choices=ContentStage.choices)
    attempt_no = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=32, choices=RunLogStatus.choices, default=RunLogStatus.RUNNING)
    triggered_by = models.CharField(max_length=32, choices=TriggeredBy.choices, default=TriggeredBy.SYSTEM)
    triggered_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="run_logs",
    )
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    error_code = models.CharField(max_length=64, null=True, blank=True)
    error_summary = models.TextField(null=True, blank=True)
    retryable = models.BooleanField(default=False)
    context_json = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "tb_run_log"
        indexes = [
            models.Index(fields=["run_id"]),
            models.Index(fields=["content_item"]),
            models.Index(fields=["content_item", "stage", "status"]),
            models.Index(fields=["discovery_run"]),
        ]

    def __str__(self) -> str:
        return f"{self.run_id}:{self.stage}:{self.status}"
