from __future__ import annotations

import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class CreatedAtModel(UUIDModel):
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class TimeStampedModel(CreatedAtModel):
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class User(TimeStampedModel, AbstractUser):
    email = models.EmailField(max_length=255, unique=True, null=True, blank=True)
    display_name = models.CharField(max_length=128, default="Admin")
    is_platform_admin = models.BooleanField(default=True)

    class Meta(AbstractUser.Meta):
        db_table = "tb_user"
        verbose_name = "User"
        verbose_name_plural = "Users"
        indexes = [
            models.Index(fields=["is_active"], name="idx_tb_user_is_active"),
        ]

    @property
    def last_login_at(self):
        return self.last_login

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        if not self.display_name:
            self.display_name = self.username or "Admin"
        super().save(*args, **kwargs)


class IdempotencyKeyStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"


class IdempotencyKey(TimeStampedModel):
    key = models.CharField(max_length=255)
    operator_scope = models.CharField(max_length=128)
    action = models.CharField(max_length=64)
    request_method = models.CharField(max_length=8, default="POST")
    request_path = models.CharField(max_length=255, blank=True)
    request_hash = models.CharField(max_length=64, blank=True)
    request_id = models.CharField(max_length=64, blank=True)
    status = models.CharField(
        max_length=16,
        choices=IdempotencyKeyStatus.choices,
        default=IdempotencyKeyStatus.PENDING,
    )
    response_code = models.CharField(max_length=64, blank=True)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "tb_idempotency_key"
        verbose_name = "Idempotency Key"
        verbose_name_plural = "Idempotency Keys"
        constraints = [
            models.UniqueConstraint(
                fields=["key", "operator_scope", "action"],
                name="uk_tb_idempotency_key_scope_action",
            ),
        ]
        indexes = [
            models.Index(fields=["operator_scope", "action"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.action}:{self.operator_scope}:{self.key}"
