from __future__ import annotations

from hashlib import sha256

import pytest
from django.utils import timezone

from techbrief.apps.content_pipeline.models import (
    ArtifactType,
    ContentArtifact,
    ContentItem,
    ContentStage,
    ContentStatus,
    ContentType,
    DiscoveryRun,
    DiscoveryRunStatus,
    DiscoveryRunType,
    EndpointContentScope,
    EndpointRole,
    EndpointType,
    Source,
    SourceEndpoint,
    TriggeredBy,
)
from techbrief.apps.content_pipeline import services as pipeline_services
from techbrief.apps.content_pipeline.services import (
    ContentPipelineService,
    DiscoveryWorkflowService,
    PipelineStageError,
    StageResult,
)
from techbrief.apps.content_pipeline.tasks import run_discovery, run_fetch
from techbrief.apps.observability.models import RunLog, RunLogStatus


@pytest.fixture
def source(db):
    return Source.objects.create(
        source_code="openai",
        source_name="OpenAI",
        base_url="https://openai.com",
        default_language="en",
    )


@pytest.fixture
def source_endpoint(source):
    return SourceEndpoint.objects.create(
        source=source,
        endpoint_type=EndpointType.RSS,
        endpoint_role=EndpointRole.PRIMARY,
        endpoint_url="https://openai.com/blog/rss.xml",
        content_type_scope=EndpointContentScope.ARTICLE,
        parser_config={
            "mock_discovery_items": [
                {
                    "title_original": "Reasoning models need better interfaces",
                    "summary_original": "A concrete article used for the workflow skeleton.",
                    "source_url": "https://openai.com/blog/reasoning-models",
                    "canonical_url": "https://openai.com/blog/reasoning-models",
                    "source_item_id": "article-001",
                    "published_at_source": timezone.now().isoformat(),
                    "content_type": ContentType.ARTICLE,
                    "metadata_json": {
                        "fetch_response": {
                            "status_code": 200,
                            "headers": {"ETag": "detail-article-001"},
                            "body": (
                                "<html><body><article><h1>Reasoning models need better interfaces</h1>"
                                "<p>Fetched article body.</p></article></body></html>"
                            ),
                        }
                    },
                }
            ]
        },
    )


@pytest.fixture
def discovery_run():
    return DiscoveryRun.objects.create(
        run_type=DiscoveryRunType.MANUAL,
        status=DiscoveryRunStatus.QUEUED,
        triggered_by=TriggeredBy.SYSTEM,
    )


@pytest.mark.django_db
def test_discovery_task_runs_workflow_to_review_pending(source_endpoint, discovery_run):
    result = run_discovery.delay(discovery_run_id=str(discovery_run.id)).get()

    discovery_run.refresh_from_db()
    content_item = ContentItem.objects.get(dedupe_key__isnull=False)

    assert result["discovered_count"] == 1
    assert result["enqueued_count"] == 1
    assert discovery_run.status == DiscoveryRunStatus.SUCCESS
    assert discovery_run.discovered_count == 1
    assert discovery_run.enqueued_count == 1

    assert content_item.source == source_endpoint.source
    assert content_item.status == ContentStatus.REVIEW_PENDING
    assert content_item.current_stage == ContentStage.REVIEW_PENDING
    assert content_item.latest_run_id == discovery_run.run_id
    assert content_item.title_zh
    assert content_item.content_md
    assert content_item.zh_md
    assert content_item.research_report_md
    assert content_item.timings_json
    assert content_item.metadata_json["fetch"]["artifacts"]
    assert content_item.metadata_json["extract"]["block_types"] == ["h1", "p", "link"]
    assert content_item.metadata_json["research"]["based_on"] == "content_md"
    assert content_item.content_ast["evidence"]["placeholder"] is True
    assert set(content_item.timings_json.keys()) == {
        ContentStage.FETCH,
        ContentStage.EXTRACT,
        ContentStage.TRANSCRIBE,
        ContentStage.TRANSLATE,
        ContentStage.RESEARCH,
        ContentStage.REVIEW_PENDING,
    }

    run_logs = list(
        RunLog.objects.filter(run_id=discovery_run.run_id).order_by("created_at", "stage")
    )
    assert len(run_logs) == 7
    assert run_logs[0].stage == ContentStage.DISCOVER
    assert run_logs[0].status == RunLogStatus.SUCCESS
    assert "endpoint_results" in run_logs[0].context_json
    assert run_logs[1].context_json["artifacts"]
    assert [log.stage for log in run_logs[1:]] == [
        ContentStage.FETCH,
        ContentStage.EXTRACT,
        ContentStage.TRANSCRIBE,
        ContentStage.TRANSLATE,
        ContentStage.RESEARCH,
        ContentStage.REVIEW_PENDING,
    ]
    assert all(log.status == RunLogStatus.SUCCESS for log in run_logs)

    source_stat = discovery_run.source_stats.get(endpoint=source_endpoint)
    assert source_stat.scanned_count == 1
    assert source_stat.new_count == 1
    assert source_stat.failed_count == 0
    assert ContentArtifact.objects.filter(
        content_item=content_item,
        artifact_type=ArtifactType.RAW_HTML,
    ).exists()
    assert ContentArtifact.objects.filter(
        content_item=content_item,
        artifact_type=ArtifactType.HTTP_RESPONSE,
    ).exists()
    assert ContentArtifact.objects.filter(
        content_item=content_item,
        artifact_type=ArtifactType.DEBUG_FILE,
    ).count() == 2


@pytest.mark.django_db
def test_stage_failure_writes_run_log_and_stops_downstream(monkeypatch, source):
    content_item = ContentItem.objects.create(
        source=source,
        source_name_snapshot=source.source_name,
        content_type=ContentType.VIDEO,
        status=ContentStatus.PROCESSING,
        current_stage=ContentStage.TRANSLATE,
        title_original="Video workflow skeleton",
        dedupe_key="f" * 64,
        source_url="https://example.com/videos/1",
    )

    def failing_translate(*, content_item: ContentItem) -> StageResult:
        raise PipelineStageError(
            "TRANSLATE_PROVIDER_TIMEOUT",
            "Translation provider timed out.",
            context={"provider": "mock-llm"},
        )

    monkeypatch.setitem(pipeline_services.STAGE_HANDLERS, ContentStage.TRANSLATE, failing_translate)

    with pytest.raises(PipelineStageError):
        ContentPipelineService.run_stage(
            content_item_id=str(content_item.id),
            stage=ContentStage.TRANSLATE,
            triggered_by=TriggeredBy.SYSTEM,
        )

    content_item.refresh_from_db()
    assert content_item.status == ContentStatus.FAILED
    assert content_item.current_stage == ContentStage.TRANSLATE
    assert content_item.last_error_code == "TRANSLATE_PROVIDER_TIMEOUT"
    assert content_item.last_error_stage == ContentStage.TRANSLATE

    run_log = RunLog.objects.get(content_item=content_item, stage=ContentStage.TRANSLATE)
    assert run_log.status == RunLogStatus.FAILED
    assert run_log.retryable is True
    assert run_log.error_code == "TRANSLATE_PROVIDER_TIMEOUT"
    assert run_log.context_json == {"provider": "mock-llm"}
    assert not RunLog.objects.filter(
        content_item=content_item,
        stage=ContentStage.RESEARCH,
    ).exists()


@pytest.mark.django_db
def test_discovery_falls_back_to_html_and_records_conditional_headers(source):
    rss_endpoint = SourceEndpoint.objects.create(
        source=source,
        endpoint_type=EndpointType.RSS,
        endpoint_role=EndpointRole.PRIMARY,
        endpoint_url="https://openai.com/blog/rss.xml",
        content_type_scope=EndpointContentScope.ARTICLE,
        last_etag='"rss-old"',
        last_modified_header="Tue, 02 Jun 2026 00:00:00 GMT",
        parser_config={
            "mock_http_response": {
                "status_code": 200,
                "headers": {
                    "ETag": '"rss-new"',
                    "Last-Modified": "Wed, 03 Jun 2026 00:00:00 GMT",
                    "Content-Type": "application/rss+xml; charset=utf-8",
                },
                "body": "<?xml version='1.0'?><rss><channel></channel></rss>",
            }
        },
    )
    html_endpoint = SourceEndpoint.objects.create(
        source=source,
        endpoint_type=EndpointType.HTML_LIST,
        endpoint_role=EndpointRole.FALLBACK,
        endpoint_url="https://openai.com/blog/",
        content_type_scope=EndpointContentScope.ARTICLE,
        priority=200,
        parser_config={
            "allowed_url_prefixes": ["https://openai.com/blog/"],
            "mock_http_response": {
                "status_code": 200,
                "headers": {"Content-Type": "text/html; charset=utf-8"},
                "body": (
                    "<html><body>"
                    "<a href='/blog/fallback-post' data-source-id='fallback-001' "
                    "data-published-at='2026-06-01T00:00:00+00:00'>Fallback Post</a>"
                    "</body></html>"
                ),
            },
            "detail_payloads": {
                "https://openai.com/blog/fallback-post": {
                    "summary_original": "Discovered from HTML fallback.",
                    "metadata_json": {
                        "fetch_response": {
                            "status_code": 200,
                            "headers": {"Content-Type": "text/html; charset=utf-8"},
                            "body": (
                                "<html><body><article><h1>Fallback Post</h1>"
                                "<p>HTML fallback detail snapshot.</p></article></body></html>"
                            ),
                        }
                    },
                }
            },
        },
    )
    discovery_run = DiscoveryRun.objects.create(
        run_type=DiscoveryRunType.MANUAL,
        status=DiscoveryRunStatus.QUEUED,
        triggered_by=TriggeredBy.SYSTEM,
        source_scope={"source_codes": [source.source_code]},
    )

    result = DiscoveryWorkflowService.run(discovery_run.id)

    rss_endpoint.refresh_from_db()
    content_item = ContentItem.objects.get(source_item_id="fallback-001")
    run_log = RunLog.objects.get(discovery_run=discovery_run, stage=ContentStage.DISCOVER)
    endpoint_results = run_log.context_json["endpoint_results"]

    assert result["discovered_count"] == 1
    assert result["enqueued_count"] == 1
    assert content_item.canonical_url == "https://openai.com/blog/fallback-post"
    assert rss_endpoint.last_etag == '"rss-new"'
    assert rss_endpoint.last_modified_header == "Wed, 03 Jun 2026 00:00:00 GMT"
    assert endpoint_results[0]["request_headers"]["If-None-Match"] == '"rss-old"'
    assert endpoint_results[0]["request_headers"]["If-Modified-Since"] == "Tue, 02 Jun 2026 00:00:00 GMT"
    assert endpoint_results[0]["candidate_count"] == 0
    assert endpoint_results[1]["parser"] == "html_list"
    assert endpoint_results[1]["candidate_count"] == 1
    assert discovery_run.source_stats.get(endpoint=html_endpoint).new_count == 1


@pytest.mark.django_db
def test_discovery_dedupes_processed_items_and_skips_reenqueue(source):
    dedupe_key = sha256(
        "openai|article|https://openai.com/blog/reasoning-models".encode("utf-8")
    ).hexdigest()
    existing_item = ContentItem.objects.create(
        source=source,
        source_name_snapshot=source.source_name,
        content_type=ContentType.ARTICLE,
        status=ContentStatus.PUBLISHED,
        current_stage=ContentStage.PUBLISH,
        title_original="Reasoning models need better interfaces",
        canonical_url="https://openai.com/blog/reasoning-models",
        source_item_id="article-001",
        dedupe_key=dedupe_key,
    )
    endpoint = SourceEndpoint.objects.create(
        source=source,
        endpoint_type=EndpointType.HTML_LIST,
        endpoint_role=EndpointRole.PRIMARY,
        endpoint_url="https://openai.com/blog/",
        content_type_scope=EndpointContentScope.ARTICLE,
        parser_config={
            "allowed_url_prefixes": ["https://openai.com/blog/"],
            "mock_http_response": {
                "status_code": 200,
                "headers": {"Content-Type": "text/html; charset=utf-8"},
                "body": (
                    "<html><body>"
                    "<a href='/blog/reasoning-models' data-source-id='article-001'>Primary Link</a>"
                    "<a href='/blog/reasoning-models' data-platform-id='openai-platform-001'>Duplicate Link</a>"
                    "</body></html>"
                ),
            },
        },
    )
    discovery_run = DiscoveryRun.objects.create(
        run_type=DiscoveryRunType.MANUAL,
        status=DiscoveryRunStatus.QUEUED,
        triggered_by=TriggeredBy.SYSTEM,
        source_scope={"source_codes": [source.source_code]},
    )

    result = DiscoveryWorkflowService.run(discovery_run.id)

    existing_item.refresh_from_db()
    stat = discovery_run.source_stats.get(endpoint=endpoint)

    assert result["discovered_count"] == 1
    assert result["enqueued_count"] == 0
    assert ContentItem.objects.count() == 1
    assert existing_item.status == ContentStatus.PUBLISHED
    assert existing_item.current_stage == ContentStage.PUBLISH
    assert stat.updated_count == 1
    assert stat.skipped_count == 2


@pytest.mark.django_db
def test_video_pipeline_persists_transcript_artifacts_and_research_evidence(source):
    endpoint = SourceEndpoint.objects.create(
        source=source,
        endpoint_type=EndpointType.HTML_LIST,
        endpoint_role=EndpointRole.PRIMARY,
        endpoint_url="https://openai.com/videos/",
        content_type_scope=EndpointContentScope.VIDEO,
        parser_config={
            "mock_discovery_items": [
                {
                    "title_original": "Operator demo",
                    "summary_original": "Video placeholder pipeline.",
                    "source_url": "https://openai.com/videos/operator-demo",
                    "canonical_url": "https://openai.com/videos/operator-demo",
                    "source_item_id": "video-001",
                    "published_at_source": timezone.now().isoformat(),
                    "content_type": ContentType.VIDEO,
                    "metadata_json": {
                        "fetch_response": {
                            "status_code": 200,
                            "headers": {"Content-Type": "text/html; charset=utf-8"},
                            "body": (
                                "<html><body><article><h1>Operator demo</h1>"
                                "<p>Video landing page snapshot.</p></article></body></html>"
                            ),
                        }
                    },
                }
            ]
        },
    )
    discovery_run = DiscoveryRun.objects.create(
        run_type=DiscoveryRunType.MANUAL,
        status=DiscoveryRunStatus.QUEUED,
        triggered_by=TriggeredBy.SYSTEM,
        source_scope={"source_codes": [source.source_code]},
    )

    result = run_discovery.delay(discovery_run_id=str(discovery_run.id)).get()

    content_item = ContentItem.objects.get(source_item_id="video-001")

    assert result["enqueued_count"] == 1
    assert endpoint.id is not None
    assert content_item.status == ContentStatus.REVIEW_PENDING
    assert content_item.transcript_text == "Transcript placeholder for Operator demo"
    assert content_item.transcript_segments_json["segments"][0]["speaker"] == "speaker-1"
    assert content_item.metadata_json["transcribe"]["segment_count"] == 1
    assert content_item.metadata_json["research"]["based_on"] == "transcript"
    assert "Evidence URL" in content_item.research_report_md
    assert ContentArtifact.objects.filter(
        content_item=content_item,
        artifact_type=ArtifactType.TRANSCRIPT_TEXT,
    ).exists()
    assert ContentArtifact.objects.filter(
        content_item=content_item,
        artifact_type=ArtifactType.TRANSCRIPT_SEGMENTS,
    ).exists()
