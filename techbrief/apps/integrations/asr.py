"""ASR (Automatic Speech Recognition) adapter for video transcription.

Follows the same factory + base-class + mock/real pattern as other integration adapters.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from urllib import error, request

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TranscriptSegment:
    """A single timed segment in a transcript."""

    start_ms: int
    end_ms: int
    text: str
    speaker: str = "speaker-1"


@dataclass(frozen=True)
class TranscriptResult:
    """Result from an ASR transcription call."""

    text: str
    segments: list[TranscriptSegment] = field(default_factory=list)
    language: str = "en"
    provider: str = ""
    duration_ms: int = 0
    raw_response: dict[str, Any] = field(default_factory=dict)


class BaseASRAdapter(ABC):
    """Abstract base for ASR providers."""

    provider_name = "base_asr"

    @abstractmethod
    def transcribe(self, *, audio_url: str = "", audio_bytes: bytes = b"") -> TranscriptResult:
        raise NotImplementedError


class MockASRAdapter(BaseASRAdapter):
    """Returns predictable placeholder transcript. Used in testing."""

    provider_name = "mock_asr"

    def transcribe(self, *, audio_url: str = "", audio_bytes: bytes = b"") -> TranscriptResult:
        source = audio_url or "local audio"
        return TranscriptResult(
            text=f"Mock transcript for {source}. This is placeholder ASR output for development.",
            segments=[
                TranscriptSegment(start_ms=0, end_ms=12000, text="Mock transcript segment one."),
                TranscriptSegment(start_ms=12000, end_ms=24000, text="Mock transcript segment two."),
            ],
            language="en",
            provider=self.provider_name,
            raw_response={"provider": self.provider_name, "mock": True},
        )


class WhisperASRAdapter(BaseASRAdapter):
    """Calls OpenAI Whisper API for audio transcription.

    Works with the official OpenAI Whisper endpoint or any compatible
    self-hosted Whisper service.
    """

    provider_name = "whisper_asr"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_base_url: str | None = None,
    ):
        self.api_key = api_key or getattr(settings, "ASR_API_KEY", "")
        self.api_base_url = (
            api_base_url or getattr(settings, "ASR_API_BASE_URL", "https://api.openai.com/v1")
        ).rstrip("/")

    def transcribe(self, *, audio_url: str = "", audio_bytes: bytes = b"") -> TranscriptResult:
        if not self.api_key:
            raise ASRError("ASR_API_KEY_MISSING", "ASR API key is not configured")

        if not audio_bytes and not audio_url:
            raise ASRError("ASR_NO_INPUT", "Either audio_url or audio_bytes must be provided")

        endpoint = f"{self.api_base_url}/audio/transcriptions"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        if audio_url:
            # Use URL-based transcription via JSON payload
            return self._transcribe_from_url(endpoint, audio_url, headers)
        else:
            return self._transcribe_from_bytes(endpoint, audio_bytes, headers)

    def _transcribe_from_url(
        self, endpoint: str, audio_url: str, headers: dict[str, str]
    ) -> TranscriptResult:
        # For remote audio URLs, download first then upload to Whisper API
        try:
            with request.urlopen(audio_url, timeout=60) as resp:
                audio_bytes = resp.read()
        except error.URLError as exc:
            raise ASRError("ASR_DOWNLOAD_FAILED", f"Failed to download audio: {exc}") from exc
        return self._transcribe_from_bytes(endpoint, audio_bytes, headers)

    def _transcribe_from_bytes(
        self, endpoint: str, audio_bytes: bytes, headers: dict[str, str]
    ) -> TranscriptResult:
        # Build multipart form data for Whisper API
        import uuid

        boundary = uuid.uuid4().hex
        boundary_line = f"--{boundary}\r\n"
        end_boundary = f"--{boundary}--\r\n"

        body_parts = []
        # model field
        body_parts.append(
            boundary_line
            + 'Content-Disposition: form-data; name="model"\r\n\r\nwhisper-1\r\n'
        )
        # response_format
        body_parts.append(
            boundary_line
            + 'Content-Disposition: form-data; name="response_format"\r\n\r\nverbose_json\r\n'
        )
        # file field
        body_parts.append(
            boundary_line
            + 'Content-Disposition: form-data; name="file"; filename="audio.mp3"\r\n'
            + "Content-Type: application/octet-stream\r\n\r\n"
        )
        body_bytes = (
            "".join(body_parts).encode("utf-8") + audio_bytes + b"\r\n" + end_boundary.encode("utf-8")
        )

        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        req = request.Request(endpoint, data=body_bytes, headers=headers, method="POST")

        try:
            with request.urlopen(req, timeout=300) as response:
                raw_body = response.read().decode("utf-8") or "{}"
        except error.HTTPError as exc:
            raw_body = exc.read().decode("utf-8", errors="ignore")
            raise ASRError(
                "ASR_HTTP_ERROR",
                f"ASR API returned HTTP {exc.code}",
                details={"body": raw_body},
            ) from exc
        except error.URLError as exc:
            raise ASRError("ASR_NETWORK_ERROR", "network error calling ASR API") from exc

        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise ASRError("ASR_INVALID_RESPONSE", "ASR API returned invalid JSON") from exc

        text = data.get("text", "")
        segments = []
        for seg in data.get("segments", []):
            segments.append(
                TranscriptSegment(
                    start_ms=int(seg.get("start", 0) * 1000),
                    end_ms=int(seg.get("end", 0) * 1000),
                    text=seg.get("text", ""),
                )
            )
        return TranscriptResult(
            text=text,
            segments=segments,
            language=data.get("language", "en"),
            provider=self.provider_name,
            duration_ms=int(data.get("duration", 0) * 1000),
            raw_response=data,
        )


class ASRError(RuntimeError):
    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def get_asr_adapter() -> BaseASRAdapter:
    """Factory: return the configured ASR adapter."""
    adapter_name = getattr(settings, "ASR_ADAPTER", "mock").strip().lower()
    if adapter_name == "whisper":
        return WhisperASRAdapter()
    return MockASRAdapter()
