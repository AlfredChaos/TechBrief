"""Cloud Object Storage backend for content artifacts.

Wraps Tencent Cloud COS (qcloud_cos) with a simple put/get interface.
When COS is not enabled, falls back to local artifact registry (DB-only records).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class StorageResult:
    """Result of a storage put operation."""

    storage_provider: str
    bucket_name: str
    storage_key: str
    size_bytes: int
    sha256: str


class CosStorageBackend:
    """Tencent Cloud COS storage backend using the cos-python-sdk-v5 client."""

    def __init__(self) -> None:
        config = settings.COS_CONFIG
        self._secret_id = config["secret_id"]
        self._secret_key = config["secret_key"]
        self._region = config["region"]
        self._bucket = config["bucket"]
        self._key_prefix = config.get("key_prefix", "techbrief")
        self._domain = config.get("domain", "")
        self._client: Any = None

    @property
    def client(self) -> Any:
        if self._client is None:
            import qcloud_cos

            self._client = qcloud_cos.CosS3Client(
                qcloud_cos.CosConfig(
                    Region=self._region,
                    SecretId=self._secret_id,
                    SecretKey=self._secret_key,
                )
            )
        return self._client

    def put_object(
        self,
        *,
        storage_key: str,
        body: bytes,
        content_type: str = "application/octet-stream",
    ) -> StorageResult:
        full_key = f"{self._key_prefix}/{storage_key}" if self._key_prefix else storage_key
        self.client.put_object(
            Bucket=self._bucket,
            Key=full_key,
            Body=body,
            ContentType=content_type,
        )
        logger.info("COS put_object: bucket=%s key=%s size=%d", self._bucket, full_key, len(body))
        return StorageResult(
            storage_provider="tencent_cos",
            bucket_name=self._bucket,
            storage_key=full_key,
            size_bytes=len(body),
            sha256="",
        )

    def get_public_url(self, storage_key: str) -> str:
        if self._domain:
            return f"{self._domain}/{storage_key}"
        return f"https://{self._bucket}.cos.{self._region}.myqcloud.com/{storage_key}"


class LocalRegistryBackend:
    """No-op storage backend that only records metadata in the database.

    Used when COS is disabled (local development, testing).
    """

    STORAGE_PROVIDER = "local_artifact_registry"
    BUCKET_NAME = "techbrief-local-artifacts"

    def put_object(
        self,
        *,
        storage_key: str,
        body: bytes,
        content_type: str = "application/octet-stream",
    ) -> StorageResult:
        return StorageResult(
            storage_provider=self.STORAGE_PROVIDER,
            bucket_name=self.BUCKET_NAME,
            storage_key=storage_key,
            size_bytes=len(body),
            sha256="",
        )


def get_storage_backend() -> CosStorageBackend | LocalRegistryBackend:
    """Return the configured storage backend based on COS_ENABLED setting."""
    if getattr(settings, "COS_ENABLED", False):
        return CosStorageBackend()
    return LocalRegistryBackend()
