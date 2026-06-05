from __future__ import annotations

import uuid

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from techbrief.apps.content_pipeline.models import ContentItem, ContentType, Source
from techbrief.apps.core.models import IdempotencyKey, User
from techbrief.apps.publishers.models import EmailDelivery, EmailDigestBatch, Subscriber


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username="operator",
        email="operator@example.com",
        password="secret-123",
        display_name="Operator",
    )


@pytest.fixture
def source(db):
    return Source.objects.create(source_code="openai", source_name="OpenAI")


@pytest.fixture
def content_item(db, source):
    return ContentItem.objects.create(
        source=source,
        source_name_snapshot="OpenAI",
        content_type=ContentType.ARTICLE,
        title_original="OpenAI Update",
        dedupe_key="a" * 64,
    )


@pytest.mark.django_db
def test_idempotency_key_is_unique_per_key_scope_and_action():
    IdempotencyKey.objects.create(
        key="idem-1",
        operator_scope="admin:1",
        action="publish_web",
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            IdempotencyKey.objects.create(
                key="idem-1",
                operator_scope="admin:1",
                action="publish_web",
            )

    IdempotencyKey.objects.create(
        key="idem-1",
        operator_scope="admin:1",
        action="retry_translate",
    )


@pytest.mark.django_db
def test_content_item_uses_audit_timestamps(content_item):
    original_updated_at = content_item.updated_at
    content_item.title_zh = "OpenAI 更新"
    content_item.save()
    content_item.refresh_from_db()

    assert content_item.created_at is not None
    assert content_item.updated_at >= original_updated_at


@pytest.mark.django_db
def test_subscriber_email_is_normalized_and_unique_case_insensitive():
    subscriber = Subscriber.objects.create(
        email="Reader@Example.COM",
        unsubscribe_token="token-1",
    )
    assert subscriber.email == "reader@example.com"

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Subscriber.objects.create(
                email="reader@example.com",
                unsubscribe_token="token-2",
            )


@pytest.mark.django_db
def test_email_delivery_is_unique_per_batch_and_subscriber(content_item):
    subscriber = Subscriber.objects.create(email="deliver@example.com", unsubscribe_token="token-deliver")
    batch = EmailDigestBatch.objects.create(batch_date=timezone.now().date())
    EmailDelivery.objects.create(batch=batch, subscriber=subscriber)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EmailDelivery.objects.create(batch=batch, subscriber=subscriber)


@pytest.mark.django_db
def test_user_email_is_normalized(admin_user):
    assert admin_user.email == "operator@example.com"
    assert admin_user.id is not None
    assert isinstance(admin_user.id, uuid.UUID)
