from __future__ import annotations

import json
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from hashlib import sha256
from html.parser import HTMLParser
from time import perf_counter
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from techbrief.apps.content_pipeline.models import (
    ArtifactType,
    ContentItem,
    ContentArtifact,
    ContentStage,
    ContentStatus,
    ContentType,
    DiscoveryRun,
    DiscoveryRunSourceStat,
    DiscoveryRunStatus,
    EndpointContentScope,
    EndpointRole,
    EndpointType,
    Source,
    SourceEndpoint,
    TextSourceStatus,
    TriggeredBy,
)
from techbrief.apps.observability.models import RunLog, RunLogStatus

RETRYABLE_STAGES = {
    ContentStage.FETCH,
    ContentStage.EXTRACT,
    ContentStage.TRANSCRIBE,
    ContentStage.TRANSLATE,
    ContentStage.RESEARCH,
}

STAGE_SEQUENCE = {
    ContentStage.FETCH: ContentStage.EXTRACT,
    ContentStage.EXTRACT: ContentStage.TRANSCRIBE,
    ContentStage.TRANSCRIBE: ContentStage.TRANSLATE,
    ContentStage.TRANSLATE: ContentStage.RESEARCH,
    ContentStage.RESEARCH: ContentStage.REVIEW_PENDING,
    ContentStage.REVIEW_PENDING: None,
}


@dataclass
class StageResult:
    content_updates: dict[str, Any] = field(default_factory=dict)
    log_context: dict[str, Any] = field(default_factory=dict)
    next_stage: str | None = None
    artifact_specs: list["ArtifactSpec"] = field(default_factory=list)


@dataclass
class ArtifactSpec:
    artifact_type: str
    body: str | bytes
    content_type: str
    file_ext: str | None = None
    language: str | None = None
    is_primary: bool = False
    storage_label: str | None = None


class PipelineStageError(Exception):
    def __init__(
        self,
        error_code: str,
        summary: str,
        *,
        retryable: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(summary)
        self.error_code = error_code
        self.summary = summary
        self.retryable = retryable
        self.context = context or {}


class _HTMLDiscoveryParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict[str, Any]] = []
        self._current_link: dict[str, Any] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attr_map = dict(attrs)
        href = attr_map.get("href")
        if not href:
            return
        self._current_link = {
            "href": href,
            "text": "",
            "attrs": attr_map,
        }

    def handle_data(self, data: str) -> None:
        if self._current_link is not None:
            self._current_link["text"] += data

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._current_link is not None:
            self.links.append(self._current_link)
            self._current_link = None


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _local_name(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _coerce_headers(headers: Any) -> dict[str, str]:
    if headers is None:
        return {}
    if isinstance(headers, dict):
        return {str(key): str(value) for key, value in headers.items()}
    return {str(key): str(value) for key, value in headers.items()}


def _build_conditional_request_headers(endpoint: SourceEndpoint) -> dict[str, str]:
    public_base_url = getattr(settings, "PUBLIC_BASE_URL", "http://localhost")
    headers = {"User-Agent": f"TechBriefBot/0.1 (+{public_base_url})"}
    if endpoint.last_etag:
        headers["If-None-Match"] = endpoint.last_etag
    if endpoint.last_modified_header:
        headers["If-Modified-Since"] = endpoint.last_modified_header
    return headers


def _decode_http_body(body: bytes, content_type: str | None) -> str:
    charset = "utf-8"
    if content_type and "charset=" in content_type:
        charset = content_type.split("charset=", 1)[1].split(";", 1)[0].strip() or "utf-8"
    try:
        return body.decode(charset)
    except (LookupError, UnicodeDecodeError):
        return body.decode("utf-8", errors="replace")


def _fetch_endpoint_payload(endpoint: SourceEndpoint) -> dict[str, Any]:
    parser_config = endpoint.parser_config or {}
    request_headers = _build_conditional_request_headers(endpoint)
    mock_response = parser_config.get("mock_http_response")
    if mock_response:
        body = mock_response.get("body") or ""
        headers = _coerce_headers(mock_response.get("headers"))
        content_type = mock_response.get("content_type") or headers.get("Content-Type")
        return {
            "status_code": int(mock_response.get("status_code", 200)),
            "url": endpoint.endpoint_url,
            "headers": headers,
            "body": str(body),
            "content_type": content_type,
            "request_headers": request_headers,
            "transport": "mock_http_response",
        }

    request = Request(endpoint.endpoint_url, headers=request_headers, method="GET")
    try:
        with urlopen(request, timeout=15) as response:
            raw_body = response.read()
            headers = _coerce_headers(response.headers)
            content_type = headers.get("Content-Type")
            return {
                "status_code": int(getattr(response, "status", 200)),
                "url": response.geturl(),
                "headers": headers,
                "body": _decode_http_body(raw_body, content_type),
                "content_type": content_type,
                "request_headers": request_headers,
                "transport": "live_http",
            }
    except HTTPError as exc:
        if exc.code == 304:
            return {
                "status_code": 304,
                "url": endpoint.endpoint_url,
                "headers": _coerce_headers(exc.headers),
                "body": "",
                "content_type": exc.headers.get("Content-Type") if exc.headers else None,
                "request_headers": request_headers,
                "transport": "live_http",
            }
        raise PipelineStageError(
            "DISCOVERY_HTTP_ERROR",
            f"Discovery request failed for {endpoint.endpoint_url} with status {exc.code}.",
            context={"endpoint_url": endpoint.endpoint_url, "status_code": exc.code},
        ) from exc
    except URLError as exc:
        raise PipelineStageError(
            "DISCOVERY_NETWORK_ERROR",
            f"Discovery request failed for {endpoint.endpoint_url}: {exc.reason}",
            context={"endpoint_url": endpoint.endpoint_url},
        ) from exc


def _merge_candidate_payload(candidate: dict[str, Any], payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return candidate
    merged = dict(candidate)
    payload_copy = dict(payload)
    metadata_json = dict(merged.get("metadata_json") or {})
    metadata_json.update(payload_copy.pop("metadata_json", {}) or {})
    for key, value in payload_copy.items():
        merged[key] = value
    if metadata_json:
        merged["metadata_json"] = metadata_json
    return merged


def _enrich_candidate_from_detail_payloads(
    candidate: dict[str, Any],
    *,
    parser_config: dict[str, Any],
) -> dict[str, Any]:
    detail_payloads = parser_config.get("detail_payloads") or {}
    for lookup_key in (
        candidate.get("canonical_url"),
        candidate.get("source_url"),
        candidate.get("source_item_id"),
        candidate.get("platform_item_id"),
    ):
        if lookup_key and lookup_key in detail_payloads:
            return _merge_candidate_payload(candidate, detail_payloads[lookup_key])
    return candidate


def _parse_rss_candidates(
    *,
    body: str,
    endpoint: SourceEndpoint,
    parser_config: dict[str, Any],
) -> list[dict[str, Any]]:
    root = ElementTree.fromstring(body)
    candidates: list[dict[str, Any]] = []
    for node in root.iter():
        if _local_name(node.tag) not in {"item", "entry"}:
            continue
        title = None
        link = None
        source_item_id = None
        published_at = None
        for child in list(node):
            child_name = _local_name(child.tag)
            if child_name == "title" and not title:
                title = _clean_text(child.text)
            elif child_name in {"guid", "id"} and not source_item_id:
                source_item_id = _clean_text(child.text)
            elif child_name in {"pubDate", "published", "updated"} and not published_at:
                published_at = _clean_text(child.text)
            elif child_name == "link" and not link:
                link = _clean_text(child.text) or _clean_text(child.attrib.get("href"))
        if not link:
            continue
        candidate = {
            "title_original": title or link,
            "source_url": urljoin(endpoint.endpoint_url, link),
            "canonical_url": urljoin(endpoint.endpoint_url, link),
            "source_item_id": source_item_id,
            "published_at_source": published_at,
            "metadata_json": {
                "discover": {
                    "parser": "rss",
                    "endpoint_url": endpoint.endpoint_url,
                }
            },
        }
        candidates.append(_enrich_candidate_from_detail_payloads(candidate, parser_config=parser_config))
    return candidates


def _parse_html_candidates(
    *,
    body: str,
    endpoint: SourceEndpoint,
    parser_config: dict[str, Any],
) -> list[dict[str, Any]]:
    parser = _HTMLDiscoveryParser()
    parser.feed(body)
    allowed_url_prefixes = parser_config.get("allowed_url_prefixes") or []
    default_content_type = parser_config.get("content_type")
    candidates: list[dict[str, Any]] = []
    for link_data in parser.links:
        attrs = link_data["attrs"]
        href = _clean_text(link_data.get("href"))
        if not href:
            continue
        source_url = urljoin(endpoint.endpoint_url, href)
        if allowed_url_prefixes and not any(source_url.startswith(prefix) for prefix in allowed_url_prefixes):
            continue
        candidate = {
            "title_original": _clean_text(link_data.get("text")) or source_url,
            "source_url": source_url,
            "canonical_url": _clean_text(attrs.get("data-canonical-url")) or source_url,
            "source_item_id": _clean_text(
                attrs.get("data-source-id") or attrs.get("data-platform-id") or attrs.get("data-item-id")
            ),
            "platform_item_id": _clean_text(attrs.get("data-platform-id")),
            "published_at_source": _clean_text(attrs.get("data-published-at")),
            "content_type": _clean_text(attrs.get("data-content-type")) or default_content_type,
            "metadata_json": {
                "discover": {
                    "parser": "html_list",
                    "endpoint_url": endpoint.endpoint_url,
                }
            },
        }
        candidates.append(_enrich_candidate_from_detail_payloads(candidate, parser_config=parser_config))
    return candidates


def _persist_endpoint_cache_headers(endpoint: SourceEndpoint, payload: dict[str, Any]) -> None:
    if payload["status_code"] == 304:
        return
    headers = payload.get("headers") or {}
    updated_fields: list[str] = []
    if headers.get("ETag") != endpoint.last_etag:
        endpoint.last_etag = headers.get("ETag")
        updated_fields.append("last_etag")
    if headers.get("Last-Modified") != endpoint.last_modified_header:
        endpoint.last_modified_header = headers.get("Last-Modified")
        updated_fields.append("last_modified_header")
    endpoint.last_success_at = timezone.now()
    updated_fields.extend(["last_success_at", "updated_at"])
    endpoint.save(update_fields=updated_fields)


def _default_discovery_handler(
    *,
    source: Source,
    endpoint: SourceEndpoint,
    discovery_run: DiscoveryRun,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    parser_config = endpoint.parser_config or {}
    items = parser_config.get("mock_discovery_items", [])
    if items:
        return [dict(item) for item in items], {
            "endpoint_id": str(endpoint.id),
            "endpoint_url": endpoint.endpoint_url,
            "endpoint_type": endpoint.endpoint_type,
            "endpoint_role": endpoint.endpoint_role,
            "candidate_count": len(items),
            "mode": "mock_discovery_items",
            "request_headers": _build_conditional_request_headers(endpoint),
        }

    payload = _fetch_endpoint_payload(endpoint)
    if payload["status_code"] == 304:
        return [], {
            "endpoint_id": str(endpoint.id),
            "endpoint_url": endpoint.endpoint_url,
            "endpoint_type": endpoint.endpoint_type,
            "endpoint_role": endpoint.endpoint_role,
            "candidate_count": 0,
            "mode": payload["transport"],
            "not_modified": True,
            "request_headers": payload["request_headers"],
            "response_headers": payload["headers"],
            "response_status_code": payload["status_code"],
        }

    _persist_endpoint_cache_headers(endpoint, payload)
    if endpoint.endpoint_type == EndpointType.RSS:
        parsed_items = _parse_rss_candidates(body=payload["body"], endpoint=endpoint, parser_config=parser_config)
        parser_used = "rss"
    else:
        parsed_items = _parse_html_candidates(body=payload["body"], endpoint=endpoint, parser_config=parser_config)
        parser_used = "html_list"
    return parsed_items, {
        "endpoint_id": str(endpoint.id),
        "endpoint_url": endpoint.endpoint_url,
        "endpoint_type": endpoint.endpoint_type,
        "endpoint_role": endpoint.endpoint_role,
        "candidate_count": len(parsed_items),
        "mode": payload["transport"],
        "parser": parser_used,
        "request_headers": payload["request_headers"],
        "response_headers": payload["headers"],
        "response_status_code": payload["status_code"],
    }


def _default_fetch_handler(*, content_item: ContentItem) -> StageResult:
    final_url = content_item.final_url or content_item.source_url or content_item.canonical_url
    metadata_json = dict(content_item.metadata_json or {})
    fetch_payload = dict(metadata_json.get("fetch_response") or {})
    response_headers = dict(fetch_payload.get("headers") or {})
    raw_html = fetch_payload.get("body") or (
        "<html><body>"
        f"<article><h1>{content_item.title_original}</h1>"
        f"<p>Placeholder fetch snapshot for {final_url or 'unknown source'}.</p>"
        "</article></body></html>"
    )
    metadata_json["fetch"] = {
        "placeholder": not bool(fetch_payload.get("body")),
        "fetched_at": timezone.now().isoformat(),
        "final_url": final_url,
        "response_status_code": fetch_payload.get("status_code", 200),
        "response_headers": response_headers,
    }
    return StageResult(
        content_updates={
            "final_url": final_url,
            "metadata_json": metadata_json,
        },
        log_context={"final_url": final_url, "raw_html_length": len(raw_html)},
        artifact_specs=[
            ArtifactSpec(
                artifact_type=ArtifactType.RAW_HTML,
                body=raw_html,
                content_type="text/html; charset=utf-8",
                file_ext="html",
                is_primary=True,
            ),
            ArtifactSpec(
                artifact_type=ArtifactType.HTTP_RESPONSE,
                body=json.dumps(
                    {
                        "final_url": final_url,
                        "status_code": fetch_payload.get("status_code", 200),
                        "headers": response_headers,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                content_type="application/json",
                file_ext="json",
            ),
        ],
    )


def _default_extract_handler(*, content_item: ContentItem) -> StageResult:
    content_md = content_item.content_md or (
        f"# {content_item.title_original}\n\n"
        "Extracted content placeholder.\n\n"
        f"Source: [{content_item.final_url or content_item.source_url}]"
        f"({content_item.final_url or content_item.source_url})"
    )
    content_ast = content_item.content_ast or {
        "type": "doc",
        "version": 1,
        "source": "workflow_placeholder",
        "title": content_item.title_original,
        "blocks": [
            {"type": "h1", "text": content_item.title_original},
            {"type": "p", "text": "Extracted content placeholder."},
            {
                "type": "link",
                "text": "Source",
                "url": content_item.final_url or content_item.source_url or content_item.canonical_url,
            },
        ],
        "evidence": {
            "placeholder": True,
            "source_url": content_item.final_url or content_item.source_url or content_item.canonical_url,
            "text_source_status": (
                TextSourceStatus.HTML if content_item.content_type == ContentType.ARTICLE else TextSourceStatus.NONE
            ),
        },
    }
    text_source_status = (
        TextSourceStatus.HTML if content_item.content_type == ContentType.ARTICLE else TextSourceStatus.NONE
    )
    metadata_json = dict(content_item.metadata_json or {})
    metadata_json["extract"] = {
        "placeholder": True,
        "block_types": [block["type"] for block in content_ast.get("blocks", [])],
        "source_kind": "html" if content_item.content_type == ContentType.ARTICLE else "video_metadata",
    }
    return StageResult(
        content_updates={
            "content_md": content_md,
            "content_ast": content_ast,
            "text_source_status": text_source_status,
            "metadata_json": metadata_json,
        },
        log_context={"content_length": len(content_md)},
        artifact_specs=[
            ArtifactSpec(
                artifact_type=ArtifactType.DEBUG_FILE,
                body=json.dumps(content_ast, ensure_ascii=False, indent=2),
                content_type="application/json",
                file_ext="json",
                storage_label="extract-evidence",
            )
        ],
    )


def _default_transcribe_handler(*, content_item: ContentItem) -> StageResult:
    transcript_text = content_item.transcript_text
    text_source_status = content_item.text_source_status
    transcript_language = content_item.transcript_language or content_item.original_language or "en"
    transcript_segments_json = content_item.transcript_segments_json
    metadata_json = dict(content_item.metadata_json or {})
    artifact_specs: list[ArtifactSpec] = []
    if content_item.content_type == ContentType.VIDEO:
        transcript_text = transcript_text or f"Transcript placeholder for {content_item.title_original}"
        transcript_segments_json = transcript_segments_json or {
            "segments": [
                {
                    "start_ms": 0,
                    "end_ms": 12000,
                    "text": transcript_text,
                    "speaker": "speaker-1",
                }
            ],
            "evidence": {
                "placeholder": True,
                "provider": "mock-asr",
                "derived_from": content_item.source_url or content_item.canonical_url,
            },
        }
        text_source_status = TextSourceStatus.ASR
        metadata_json["transcribe"] = {
            "placeholder": True,
            "provider": "mock-asr",
            "segment_count": len(transcript_segments_json["segments"]),
            "text_source_status": text_source_status,
        }
        artifact_specs = [
            ArtifactSpec(
                artifact_type=ArtifactType.TRANSCRIPT_TEXT,
                body=transcript_text,
                content_type="text/plain; charset=utf-8",
                file_ext="txt",
                language=transcript_language,
                is_primary=True,
            ),
            ArtifactSpec(
                artifact_type=ArtifactType.TRANSCRIPT_SEGMENTS,
                body=json.dumps(transcript_segments_json, ensure_ascii=False, indent=2),
                content_type="application/json",
                file_ext="json",
                language=transcript_language,
            ),
        ]
    else:
        metadata_json["transcribe"] = {
            "placeholder": False,
            "skipped": True,
            "reason": "non_video_content",
            "text_source_status": text_source_status,
        }
    return StageResult(
        content_updates={
            "transcript_text": transcript_text,
            "transcript_segments_json": transcript_segments_json,
            "transcript_language": transcript_language,
            "transcription_confidence": content_item.transcription_confidence or 0.9900,
            "text_source_status": text_source_status,
            "metadata_json": metadata_json,
        },
        log_context={"transcript_available": bool(transcript_text)},
        artifact_specs=artifact_specs,
    )


def _default_translate_handler(*, content_item: ContentItem) -> StageResult:
    title_zh = content_item.title_zh or f"ZH: {content_item.title_original}"
    summary_zh = content_item.summary_zh or content_item.summary_original or "Translated summary placeholder."
    zh_md = content_item.zh_md or f"## {title_zh}\n\nTranslated body placeholder."
    zh_ast = content_item.zh_ast or {
        "type": "doc",
        "source": "workflow_skeleton",
        "lang": "zh-CN",
    }
    metadata_json = dict(content_item.metadata_json or {})
    metadata_json["translate"] = {
        "placeholder": True,
        "supports_bilingual": True,
    }
    return StageResult(
        content_updates={
            "title_zh": title_zh,
            "summary_zh": summary_zh,
            "zh_md": zh_md,
            "zh_ast": zh_ast,
            "supports_bilingual": True,
            "metadata_json": metadata_json,
        },
        log_context={"translated": True},
    )


def _default_research_handler(*, content_item: ContentItem) -> StageResult:
    research_report_md = content_item.research_report_md or (
        f"## Research Notes\n\n- Source: {content_item.source_name_snapshot}\n"
        f"- Title: {content_item.title_original}\n"
        f"- Based on: {'transcript' if content_item.transcript_text else 'content body'}\n"
        f"- Evidence URL: {content_item.final_url or content_item.source_url or content_item.canonical_url}\n"
        "- Status: generated by workflow placeholder\n"
    )
    metadata_json = dict(content_item.metadata_json or {})
    metadata_json["research"] = {
        "placeholder": True,
        "based_on": "transcript" if content_item.transcript_text else "content_md",
        "has_transcript": bool(content_item.transcript_text),
    }
    return StageResult(
        content_updates={
            "research_report_md": research_report_md,
            "metadata_json": metadata_json,
        },
        log_context={"report_length": len(research_report_md)},
        artifact_specs=[
            ArtifactSpec(
                artifact_type=ArtifactType.DEBUG_FILE,
                body=json.dumps(metadata_json["research"], ensure_ascii=False, indent=2),
                content_type="application/json",
                file_ext="json",
                storage_label="research-evidence",
            )
        ],
    )


def _default_review_pending_handler(*, content_item: ContentItem) -> StageResult:
    return StageResult(log_context={"review_ready": True})


DISCOVERY_HANDLER = _default_discovery_handler
STAGE_HANDLERS = {
    ContentStage.FETCH: _default_fetch_handler,
    ContentStage.EXTRACT: _default_extract_handler,
    ContentStage.TRANSCRIBE: _default_transcribe_handler,
    ContentStage.TRANSLATE: _default_translate_handler,
    ContentStage.RESEARCH: _default_research_handler,
    ContentStage.REVIEW_PENDING: _default_review_pending_handler,
}


def _merge_timings(
    timings_json: dict[str, Any] | None,
    *,
    stage: str,
    duration_ms: int,
) -> dict[str, Any]:
    merged = dict(timings_json or {})
    merged[stage] = {
        "duration_ms": duration_ms,
        "completed_at": timezone.now().isoformat(),
    }
    return merged


def _normalize_datetime(value: Any) -> Any:
    if isinstance(value, str):
        return parse_datetime(value)
    return value


def _build_dedupe_key(*, source: Source, content_type: str, candidate: dict[str, Any]) -> str:
    identity = (
        candidate.get("canonical_url")
        or candidate.get("source_item_id")
        or candidate.get("platform_item_id")
        or candidate.get("source_url")
        or candidate.get("title_original")
        or ""
    )
    raw = "|".join(
        [
            source.source_code,
            content_type,
            str(identity),
        ]
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def _resolve_content_type(endpoint: SourceEndpoint, candidate: dict[str, Any]) -> str:
    content_type = candidate.get("content_type")
    if content_type in {ContentType.ARTICLE, ContentType.VIDEO, ContentType.MANUAL}:
        return content_type
    if endpoint.content_type_scope == EndpointContentScope.VIDEO:
        return ContentType.VIDEO
    return ContentType.ARTICLE


def _should_enqueue_content_item(*, content_item: ContentItem, created: bool) -> bool:
    if created:
        return True
    return (
        content_item.status == ContentStatus.DISCOVERED
        and content_item.current_stage == ContentStage.DISCOVER
    )


def _normalize_discovery_handler_result(result: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if isinstance(result, tuple) and len(result) == 2:
        items, context = result
        return list(items), dict(context or {})
    return list(result), {}


def _persist_stage_artifacts(
    *,
    content_item: ContentItem,
    stage: str,
    artifact_specs: list[ArtifactSpec],
) -> list[dict[str, Any]]:
    persisted: list[dict[str, Any]] = []
    for spec in artifact_specs:
        body = spec.body.encode("utf-8") if isinstance(spec.body, str) else spec.body
        file_ext = spec.file_ext or "bin"
        storage_label = spec.storage_label or spec.artifact_type
        storage_key = f"content-items/{content_item.id}/{stage}/{storage_label}.{file_ext}"
        sha = sha256(body).hexdigest()
        artifact, _ = ContentArtifact.objects.update_or_create(
            storage_key=storage_key,
            defaults={
                "content_item": content_item,
                "artifact_type": spec.artifact_type,
                "storage_provider": "local_artifact_registry",
                "bucket_name": "techbrief-local-artifacts",
                "content_type": spec.content_type,
                "file_ext": file_ext,
                "language": spec.language,
                "size_bytes": len(body),
                "sha256": sha,
                "is_primary": spec.is_primary,
            },
        )
        persisted.append(
            {
                "artifact_type": artifact.artifact_type,
                "storage_key": artifact.storage_key,
                "content_type": artifact.content_type,
                "size_bytes": artifact.size_bytes,
                "sha256": artifact.sha256,
            }
        )
    return persisted


class DiscoveryWorkflowService:
    @staticmethod
    def run(discovery_run_id: str | uuid.UUID) -> dict[str, Any]:
        discovery_run = DiscoveryRun.objects.select_related("triggered_by_user").get(id=discovery_run_id)
        started_at = timezone.now()
        timer = perf_counter()
        run_log = RunLog.objects.create(
            run_id=discovery_run.run_id,
            request_id=discovery_run.request_id,
            discovery_run=discovery_run,
            stage=ContentStage.DISCOVER,
            status=RunLogStatus.RUNNING,
            triggered_by=discovery_run.triggered_by,
            triggered_by_user=discovery_run.triggered_by_user,
            started_at=started_at,
        )
        discovery_run.status = DiscoveryRunStatus.RUNNING
        discovery_run.started_at = discovery_run.started_at or started_at
        discovery_run.error_code = None
        discovery_run.error_message = None
        discovery_run.save(
            update_fields=[
                "status",
                "started_at",
                "error_code",
                "error_message",
                "updated_at",
            ]
        )

        content_item_ids: list[str] = []
        discovered_count = 0
        updated_count = 0
        failed_count = 0
        seen_dedupe_keys: set[str] = set()
        endpoint_results: list[dict[str, Any]] = []

        try:
            grouped_endpoints: dict[str, list[SourceEndpoint]] = defaultdict(list)
            for endpoint in DiscoveryWorkflowService._iter_enabled_endpoints(discovery_run):
                grouped_endpoints[str(endpoint.source_id)].append(endpoint)

            for endpoints in grouped_endpoints.values():
                source_has_candidates = False
                primary_not_modified = False
                for endpoint in endpoints:
                    source = endpoint.source
                    stat, _ = DiscoveryRunSourceStat.objects.get_or_create(
                        discovery_run=discovery_run,
                        source=source,
                        endpoint=endpoint,
                    )

                    if endpoint.endpoint_role == EndpointRole.FALLBACK and (source_has_candidates or primary_not_modified):
                        stat.skipped_count += 1
                        stat.save(update_fields=["skipped_count"])
                        endpoint_results.append(
                            {
                                "endpoint_id": str(endpoint.id),
                                "endpoint_url": endpoint.endpoint_url,
                                "endpoint_role": endpoint.endpoint_role,
                                "skipped": True,
                                "skip_reason": "primary_endpoint_satisfied_source",
                            }
                        )
                        continue

                    try:
                        raw_result = DISCOVERY_HANDLER(
                            source=source,
                            endpoint=endpoint,
                            discovery_run=discovery_run,
                        )
                        candidates, endpoint_context = _normalize_discovery_handler_result(raw_result)
                    except PipelineStageError as exc:
                        failed_count += 1
                        stat.failed_count += 1
                        stat.last_error_code = exc.error_code
                        stat.last_error_message = exc.summary
                        stat.save(
                            update_fields=[
                                "failed_count",
                                "last_error_code",
                                "last_error_message",
                            ]
                        )
                        endpoint_results.append(
                            {
                                "endpoint_id": str(endpoint.id),
                                "endpoint_url": endpoint.endpoint_url,
                                "endpoint_role": endpoint.endpoint_role,
                                "error_code": exc.error_code,
                                "error_summary": exc.summary,
                            }
                        )
                        continue

                    if endpoint_context.get("not_modified") and endpoint.endpoint_role == EndpointRole.PRIMARY:
                        primary_not_modified = True
                    endpoint_results.append(endpoint_context or {"endpoint_id": str(endpoint.id)})

                    stat.scanned_count += len(candidates)
                    stat.last_error_code = None
                    stat.last_error_message = None

                    for candidate in candidates:
                        content_type = _resolve_content_type(endpoint, candidate)
                        dedupe_key = candidate.get("dedupe_key") or _build_dedupe_key(
                            source=source,
                            content_type=content_type,
                            candidate=candidate,
                        )
                        if dedupe_key in seen_dedupe_keys:
                            stat.skipped_count += 1
                            continue
                        seen_dedupe_keys.add(dedupe_key)

                        item, created = DiscoveryWorkflowService._upsert_content_item(
                            source=source,
                            endpoint=endpoint,
                            candidate=candidate,
                            dedupe_key=dedupe_key,
                            content_type=content_type,
                        )
                        discovered_count += 1
                        if created:
                            stat.new_count += 1
                        else:
                            stat.updated_count += 1
                            updated_count += 1

                        if _should_enqueue_content_item(content_item=item, created=created):
                            content_item_ids.append(str(item.id))
                        else:
                            stat.skipped_count += 1

                    if candidates:
                        source_has_candidates = True
                    stat.save(
                        update_fields=[
                            "scanned_count",
                            "new_count",
                            "updated_count",
                            "skipped_count",
                            "last_error_code",
                            "last_error_message",
                        ]
                    )

            discovery_run.discovered_count = discovered_count
            discovery_run.enqueued_count = len(content_item_ids)
            discovery_run.updated_count = updated_count
            discovery_run.failed_count = failed_count
            discovery_run.ended_at = timezone.now()
            discovery_run.status = (
                DiscoveryRunStatus.PARTIAL_FAILED if failed_count else DiscoveryRunStatus.SUCCESS
            )
            discovery_run.save(
                update_fields=[
                    "discovered_count",
                    "enqueued_count",
                    "updated_count",
                    "failed_count",
                    "ended_at",
                    "status",
                    "updated_at",
                ]
            )
            duration_ms = max(int((perf_counter() - timer) * 1000), 0)
            run_log.status = RunLogStatus.SUCCESS
            run_log.ended_at = timezone.now()
            run_log.duration_ms = duration_ms
            run_log.context_json = {
                "discovered_count": discovered_count,
                "enqueued_count": len(content_item_ids),
                "failed_count": failed_count,
                "content_item_ids": content_item_ids,
                "endpoint_results": endpoint_results,
            }
            run_log.save(update_fields=["status", "ended_at", "duration_ms", "context_json"])
            return {
                "run_id": str(discovery_run.run_id),
                "discovery_run_id": str(discovery_run.id),
                "content_item_ids": content_item_ids,
                "discovered_count": discovered_count,
                "enqueued_count": len(content_item_ids),
                "failed_count": failed_count,
            }
        except Exception as exc:
            duration_ms = max(int((perf_counter() - timer) * 1000), 0)
            discovery_run.status = DiscoveryRunStatus.FAILED
            discovery_run.failed_count = failed_count + 1
            discovery_run.ended_at = timezone.now()
            discovery_run.error_code = "DISCOVER_FAILED"
            discovery_run.error_message = str(exc)
            discovery_run.save(
                update_fields=[
                    "status",
                    "failed_count",
                    "ended_at",
                    "error_code",
                    "error_message",
                    "updated_at",
                ]
            )
            run_log.status = RunLogStatus.FAILED
            run_log.ended_at = timezone.now()
            run_log.duration_ms = duration_ms
            run_log.error_code = "DISCOVER_FAILED"
            run_log.error_summary = str(exc)
            run_log.context_json = {"failed_count": discovery_run.failed_count}
            run_log.save(
                update_fields=[
                    "status",
                    "ended_at",
                    "duration_ms",
                    "error_code",
                    "error_summary",
                    "context_json",
                ]
            )
            raise

    @staticmethod
    def _iter_enabled_endpoints(discovery_run: DiscoveryRun):
        queryset = SourceEndpoint.objects.select_related("source").filter(
            is_enabled=True,
            source__is_enabled=True,
        )
        source_scope = discovery_run.source_scope or {}
        source_codes = source_scope.get("source_codes") or []
        if source_codes:
            queryset = queryset.filter(source__source_code__in=source_codes)
        if source_scope.get("source_code"):
            queryset = queryset.filter(source__source_code=source_scope["source_code"])
        if source_scope.get("endpoint_id"):
            queryset = queryset.filter(id=source_scope["endpoint_id"])
        return queryset.order_by("source__source_code", "priority", "created_at")

    @staticmethod
    def _upsert_content_item(
        *,
        source: Source,
        endpoint: SourceEndpoint,
        candidate: dict[str, Any],
        dedupe_key: str,
        content_type: str,
    ) -> tuple[ContentItem, bool]:
        defaults = {
            "source": source,
            "source_name_snapshot": source.source_name,
            "content_type": content_type,
            "title_original": candidate.get("title_original") or "Untitled discovery item",
            "title_zh": candidate.get("title_zh"),
            "summary_original": candidate.get("summary_original"),
            "summary_zh": candidate.get("summary_zh"),
            "author_or_speaker": candidate.get("author_or_speaker"),
            "source_url": candidate.get("source_url"),
            "final_url": candidate.get("final_url"),
            "canonical_url": candidate.get("canonical_url") or candidate.get("source_url"),
            "source_item_id": candidate.get("source_item_id"),
            "published_at_source": _normalize_datetime(candidate.get("published_at_source")),
            "original_language": candidate.get("original_language") or source.default_language,
            "text_source_status": candidate.get("text_source_status") or TextSourceStatus.NONE,
            "content_ast": candidate.get("content_ast"),
            "content_md": candidate.get("content_md"),
            "zh_ast": candidate.get("zh_ast"),
            "zh_md": candidate.get("zh_md"),
            "research_report_md": candidate.get("research_report_md"),
            "transcript_text": candidate.get("transcript_text"),
            "transcript_segments_json": candidate.get("transcript_segments_json"),
            "transcript_language": candidate.get("transcript_language"),
            "transcription_confidence": candidate.get("transcription_confidence"),
            "metadata_json": dict(candidate.get("metadata_json") or {}),
            "supports_bilingual": candidate.get("supports_bilingual", True),
        }
        item = ContentItem.objects.filter(dedupe_key=dedupe_key).first()
        if item is None:
            item = ContentItem.objects.create(
                dedupe_key=dedupe_key,
                status=ContentStatus.DISCOVERED,
                current_stage=ContentStage.DISCOVER,
                last_error_code=None,
                last_error_message=None,
                last_error_stage=None,
                **defaults,
            )
            return item, True

        updates: dict[str, Any] = {}
        non_destructive_fields = {
            "content_ast",
            "content_md",
            "zh_ast",
            "zh_md",
            "research_report_md",
            "transcript_text",
            "transcript_segments_json",
            "transcript_language",
            "transcription_confidence",
        }
        for field_name, value in defaults.items():
            current_value = getattr(item, field_name)
            if field_name == "metadata_json":
                merged_metadata = dict(current_value or {})
                merged_metadata.update(value or {})
                if merged_metadata != current_value:
                    updates[field_name] = merged_metadata
                continue
            if value is None:
                continue
            if field_name in non_destructive_fields and current_value not in (None, "", [], {}):
                continue
            if current_value != value:
                updates[field_name] = value

        if updates:
            for field_name, value in updates.items():
                setattr(item, field_name, value)
            item.save(update_fields=[*updates.keys(), "updated_at"])
        return item, False


class ContentPipelineService:
    @staticmethod
    def run_stage(
        *,
        content_item_id: str | uuid.UUID,
        stage: str,
        run_id: str | uuid.UUID | None = None,
        discovery_run_id: str | uuid.UUID | None = None,
        request_id: str | None = None,
        triggered_by: str = TriggeredBy.SYSTEM,
        triggered_by_user_id: str | uuid.UUID | None = None,
    ) -> dict[str, Any]:
        if stage not in STAGE_HANDLERS:
            raise ValueError(f"unsupported stage: {stage}")

        run_uuid = uuid.UUID(str(run_id)) if run_id else uuid.uuid4()
        timer = perf_counter()
        started_at = timezone.now()
        discovery_run = None
        if discovery_run_id:
            discovery_run = DiscoveryRun.objects.filter(id=discovery_run_id).first()

        with transaction.atomic():
            content_item = ContentItem.objects.select_for_update().get(id=content_item_id)
            run_log = RunLog.objects.create(
                run_id=run_uuid,
                request_id=request_id,
                content_item=content_item,
                discovery_run=discovery_run,
                stage=stage,
                status=RunLogStatus.RUNNING,
                triggered_by=triggered_by,
                triggered_by_user_id=triggered_by_user_id,
                started_at=started_at,
            )
            content_item.status = ContentStatus.PROCESSING
            content_item.current_stage = stage
            content_item.latest_run_id = run_uuid
            content_item.last_processed_at = started_at
            content_item.save(
                update_fields=[
                    "status",
                    "current_stage",
                    "latest_run_id",
                    "last_processed_at",
                    "updated_at",
                ]
            )

        content_item = ContentItem.objects.get(id=content_item_id)

        try:
            result = STAGE_HANDLERS[stage](content_item=content_item)
        except PipelineStageError as exc:
            duration_ms = max(int((perf_counter() - timer) * 1000), 0)
            retryable = exc.retryable if exc.retryable is not None else stage in RETRYABLE_STAGES
            with transaction.atomic():
                content_item = ContentItem.objects.select_for_update().get(id=content_item_id)
                run_log = RunLog.objects.select_for_update().get(id=run_log.id)
                content_item.status = ContentStatus.FAILED
                content_item.current_stage = stage
                content_item.latest_run_id = run_uuid
                content_item.last_processed_at = timezone.now()
                content_item.last_error_code = exc.error_code
                content_item.last_error_message = exc.summary
                content_item.last_error_stage = stage
                content_item.timings_json = _merge_timings(
                    content_item.timings_json,
                    stage=stage,
                    duration_ms=duration_ms,
                )
                content_item.save(
                    update_fields=[
                        "status",
                        "current_stage",
                        "latest_run_id",
                        "last_processed_at",
                        "last_error_code",
                        "last_error_message",
                        "last_error_stage",
                        "timings_json",
                        "updated_at",
                    ]
                )
                run_log.status = RunLogStatus.FAILED
                run_log.ended_at = timezone.now()
                run_log.duration_ms = duration_ms
                run_log.error_code = exc.error_code
                run_log.error_summary = exc.summary
                run_log.retryable = retryable
                run_log.context_json = exc.context
                run_log.save(
                    update_fields=[
                        "status",
                        "ended_at",
                        "duration_ms",
                        "error_code",
                        "error_summary",
                        "retryable",
                        "context_json",
                    ]
                )
            raise

        duration_ms = max(int((perf_counter() - timer) * 1000), 0)
        next_stage = result.next_stage or STAGE_SEQUENCE[stage]
        with transaction.atomic():
            content_item = ContentItem.objects.select_for_update().get(id=content_item_id)
            run_log = RunLog.objects.select_for_update().get(id=run_log.id)
            content_updates = dict(result.content_updates)
            content_updates.update(
                {
                    "latest_run_id": run_uuid,
                    "last_processed_at": timezone.now(),
                    "last_error_code": None,
                    "last_error_message": None,
                    "last_error_stage": None,
                    "timings_json": _merge_timings(
                        content_item.timings_json,
                        stage=stage,
                        duration_ms=duration_ms,
                    ),
                }
            )
            if stage == ContentStage.REVIEW_PENDING:
                content_updates["status"] = ContentStatus.REVIEW_PENDING
                content_updates["current_stage"] = ContentStage.REVIEW_PENDING
            else:
                content_updates["status"] = ContentStatus.PROCESSING
                content_updates["current_stage"] = next_stage or stage

            for field_name, value in content_updates.items():
                setattr(content_item, field_name, value)
            content_item.save(update_fields=[*content_updates.keys(), "updated_at"])
            artifact_refs = _persist_stage_artifacts(
                content_item=content_item,
                stage=stage,
                artifact_specs=result.artifact_specs,
            )
            if artifact_refs:
                metadata_json = dict(content_item.metadata_json or {})
                stage_metadata = dict(metadata_json.get(stage) or {})
                stage_metadata["artifacts"] = artifact_refs
                metadata_json[stage] = stage_metadata
                content_item.metadata_json = metadata_json
                content_item.save(update_fields=["metadata_json", "updated_at"])

            run_log.status = RunLogStatus.SUCCESS
            run_log.ended_at = timezone.now()
            run_log.duration_ms = duration_ms
            run_log.context_json = {
                **result.log_context,
                "artifacts": artifact_refs,
            }
            run_log.save(update_fields=["status", "ended_at", "duration_ms", "context_json"])
            return {
                "content_item_id": str(content_item.id),
                "run_id": str(run_uuid),
                "stage": stage,
                "next_stage": next_stage,
                "status": content_item.status,
            }
