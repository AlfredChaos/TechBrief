"""LLM adapter layer for AI-powered pipeline stages (translate, research).

Follows the same factory + base-class + mock/real pattern as email and WeChat adapters.
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
class LLMResponse:
    """Standardized response from any LLM adapter."""

    text: str
    usage: dict[str, int] = field(default_factory=dict)
    model: str = ""
    raw_response: dict[str, Any] = field(default_factory=dict)


class BaseLLMAdapter(ABC):
    """Abstract base for LLM providers."""

    provider_name = "base_llm"

    @abstractmethod
    def chat(
        self,
        prompt: str,
        *,
        system_prompt: str = "",
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        raise NotImplementedError


class MockLLMAdapter(BaseLLMAdapter):
    """Returns predictable placeholder text. Used in testing and when LLM_ADAPTER=mock."""

    provider_name = "mock_llm"

    def chat(
        self,
        prompt: str,
        *,
        system_prompt: str = "",
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        # Generate a deterministic mock response based on the prompt content
        preview = prompt[:120].replace("\n", " ").strip()
        return LLMResponse(
            text=f"[MOCK LLM RESPONSE] Based on the provided content: {preview}...",
            usage={"prompt_tokens": len(prompt) // 4, "completion_tokens": 200, "total_tokens": len(prompt) // 4 + 200},
            model="mock-llm-v1",
            raw_response={"provider": self.provider_name, "mock": True},
        )


class OpenAICompatibleAdapter(BaseLLMAdapter):
    """Calls any OpenAI-compatible chat completions endpoint.

    Works with OpenAI, Azure OpenAI, DeepSeek, local vLLM, Ollama, etc.
    Uses urllib to avoid adding the heavy openai SDK dependency.
    """

    provider_name = "openai_compatible"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_base_url: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or getattr(settings, "LLM_API_KEY", "")
        self.api_base_url = (
            api_base_url or getattr(settings, "LLM_API_BASE_URL", "https://api.openai.com/v1")
        ).rstrip("/")
        self.model = model or getattr(settings, "LLM_MODEL", "gpt-4o")

    def chat(
        self,
        prompt: str,
        *,
        system_prompt: str = "",
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        if not self.api_key:
            raise IntegrationError("LLM_API_KEY_MISSING", "LLM API key is not configured")

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        endpoint = f"{self.api_base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        raw_response = _post_json(endpoint, payload, headers=headers, timeout=120)

        choices = raw_response.get("choices", [])
        if not choices:
            raise IntegrationError("LLM_NO_CHOICES", "LLM returned no choices", details=raw_response)

        text = choices[0].get("message", {}).get("content", "")
        usage = raw_response.get("usage", {})
        return LLMResponse(
            text=text,
            usage=usage,
            model=raw_response.get("model", self.model),
            raw_response=raw_response,
        )


class IntegrationError(RuntimeError):
    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def get_llm_adapter() -> BaseLLMAdapter:
    """Factory: return the configured LLM adapter."""
    adapter_name = getattr(settings, "LLM_ADAPTER", "mock").strip().lower()
    if adapter_name == "openai_compatible":
        return OpenAICompatibleAdapter()
    return MockLLMAdapter()


def _post_json(
    url: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    request_headers = {"Content-Type": "application/json"}
    request_headers.update(headers or {})
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, headers=request_headers, method="POST")
    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw_body = response.read().decode("utf-8") or "{}"
    except error.HTTPError as exc:
        raw_body = exc.read().decode("utf-8", errors="ignore")
        raise IntegrationError(
            "LLM_HTTP_ERROR",
            f"LLM API returned HTTP {exc.code}",
            details={"body": raw_body},
        ) from exc
    except error.URLError as exc:
        raise IntegrationError("LLM_NETWORK_ERROR", "network error calling LLM API") from exc

    try:
        return json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise IntegrationError(
            "LLM_INVALID_RESPONSE",
            "LLM API returned invalid JSON",
            details={"body": raw_body},
        ) from exc
