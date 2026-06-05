from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any
from urllib import error, request

from django.conf import settings


class IntegrationError(RuntimeError):
    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


@dataclass(frozen=True)
class EmailMessage:
    to_email: str
    subject: str
    html: str
    text: str
    from_email: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EmailSendResult:
    provider_message_id: str
    provider_batch_id: str | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WeChatDraftPayload:
    title: str
    author: str
    digest: str
    content_html: str
    content_source_url: str | None = None
    thumb_media_id: str | None = None
    show_cover_pic: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WeChatDraftResult:
    draft_id: str
    raw_response: dict[str, Any] = field(default_factory=dict)


class BaseEmailAdapter:
    provider_name = "base_email"

    def send(self, message: EmailMessage) -> EmailSendResult:
        raise NotImplementedError


class BaseWeChatDraftAdapter:
    provider_name = "base_wechat"

    def create_draft(self, payload: WeChatDraftPayload) -> WeChatDraftResult:
        raise NotImplementedError


class MockEmailAdapter(BaseEmailAdapter):
    provider_name = "mock_email"

    def __init__(self, *, fail_for: set[str] | None = None):
        self.fail_for = {value.lower() for value in fail_for or set()}

    def send(self, message: EmailMessage) -> EmailSendResult:
        if message.to_email.lower() in self.fail_for:
            raise IntegrationError("MOCK_EMAIL_SEND_FAILED", "mock email delivery failed")

        digest = hashlib.sha256(
            f"{message.to_email}|{message.subject}|{json.dumps(message.metadata, sort_keys=True)}".encode("utf-8")
        ).hexdigest()
        return EmailSendResult(
            provider_message_id=f"mock-email-{digest[:16]}",
            provider_batch_id=message.metadata.get("batch_key"),
            raw_response={
                "provider": self.provider_name,
                "accepted": True,
                "to": message.to_email,
            },
        )


class ResendEmailAdapter(BaseEmailAdapter):
    provider_name = "resend"
    endpoint = "https://api.resend.com/emails"

    def __init__(self, *, api_key: str | None = None, from_email: str | None = None):
        self.api_key = api_key or getattr(settings, "RESEND_API_KEY", "")
        self.from_email = from_email or getattr(settings, "EMAIL_FROM_ADDRESS", "")

    def send(self, message: EmailMessage) -> EmailSendResult:
        if not self.api_key:
            raise IntegrationError("RESEND_API_KEY_MISSING", "resend api key is not configured")
        from_email = message.from_email or self.from_email
        if not from_email:
            raise IntegrationError("EMAIL_FROM_ADDRESS_MISSING", "from email is not configured")

        payload = {
            "from": from_email,
            "to": [message.to_email],
            "subject": message.subject,
            "html": message.html,
            "text": message.text,
            "tags": [{"name": key, "value": str(value)} for key, value in sorted(message.metadata.items())],
        }
        raw_response = _post_json(
            self.endpoint,
            payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        return EmailSendResult(
            provider_message_id=raw_response.get("id", ""),
            provider_batch_id=message.metadata.get("batch_key"),
            raw_response=raw_response,
        )


class MockWeChatDraftAdapter(BaseWeChatDraftAdapter):
    provider_name = "mock_wechat"

    def __init__(self, *, fail: bool = False):
        self.fail = fail

    def create_draft(self, payload: WeChatDraftPayload) -> WeChatDraftResult:
        if self.fail:
            raise IntegrationError("MOCK_WECHAT_DRAFT_FAILED", "mock wechat draft creation failed")

        digest = hashlib.sha256(
            f"{payload.title}|{payload.author}|{payload.digest}".encode("utf-8")
        ).hexdigest()
        return WeChatDraftResult(
            draft_id=f"mock-draft-{digest[:12]}",
            raw_response={"provider": self.provider_name, "title": payload.title},
        )


class WeChatDraftApiAdapter(BaseWeChatDraftAdapter):
    provider_name = "wechat_draft_api"

    def __init__(self, *, access_token: str | None = None, api_base_url: str | None = None):
        self.access_token = access_token or getattr(settings, "WECHAT_ACCESS_TOKEN", "")
        self.api_base_url = (
            api_base_url or getattr(settings, "WECHAT_API_BASE_URL", "https://api.weixin.qq.com")
        ).rstrip("/")

    def create_draft(self, payload: WeChatDraftPayload) -> WeChatDraftResult:
        if not self.access_token:
            raise IntegrationError("WECHAT_ACCESS_TOKEN_MISSING", "wechat access token is not configured")

        endpoint = f"{self.api_base_url}/cgi-bin/draft/add?access_token={self.access_token}"
        raw_response = _post_json(
            endpoint,
            {
                "articles": [
                    {
                        "title": payload.title,
                        "author": payload.author,
                        "digest": payload.digest,
                        "content": payload.content_html,
                        "content_source_url": payload.content_source_url or "",
                        "thumb_media_id": payload.thumb_media_id or "",
                        "show_cover_pic": 1 if payload.show_cover_pic else 0,
                    }
                ]
            },
        )
        if raw_response.get("errcode") not in (None, 0):
            raise IntegrationError(
                "WECHAT_DRAFT_CREATE_FAILED",
                raw_response.get("errmsg", "wechat draft create failed"),
                details=raw_response,
            )
        media_id = raw_response.get("media_id")
        if not media_id:
            raise IntegrationError("WECHAT_DRAFT_ID_MISSING", "wechat draft id missing", details=raw_response)
        return WeChatDraftResult(draft_id=media_id, raw_response=raw_response)


def get_email_adapter() -> BaseEmailAdapter:
    adapter_name = getattr(settings, "EMAIL_DELIVERY_ADAPTER", "mock").strip().lower()
    if adapter_name == "resend":
        return ResendEmailAdapter()
    return MockEmailAdapter()


def get_wechat_draft_adapter() -> BaseWeChatDraftAdapter:
    adapter_name = getattr(settings, "WECHAT_DRAFT_ADAPTER", "mock").strip().lower()
    if adapter_name == "wechat_api":
        return WeChatDraftApiAdapter()
    return MockWeChatDraftAdapter()


def _post_json(url: str, payload: dict[str, Any], *, headers: dict[str, str] | None = None) -> dict[str, Any]:
    request_headers = {"Content-Type": "application/json"}
    request_headers.update(headers or {})
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, headers=request_headers, method="POST")
    try:
        with request.urlopen(req, timeout=10) as response:
            raw_body = response.read().decode("utf-8") or "{}"
    except error.HTTPError as exc:
        raw_body = exc.read().decode("utf-8", errors="ignore")
        raise IntegrationError(
            "INTEGRATION_HTTP_ERROR",
            f"http error from integration: {exc.code}",
            details={"body": raw_body},
        ) from exc
    except error.URLError as exc:
        raise IntegrationError("INTEGRATION_NETWORK_ERROR", "network error calling integration") from exc

    try:
        return json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise IntegrationError(
            "INTEGRATION_INVALID_RESPONSE",
            "integration returned invalid json",
            details={"body": raw_body},
        ) from exc
