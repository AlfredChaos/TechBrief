from __future__ import annotations

from copy import deepcopy
from datetime import date
import json
import re
from pathlib import Path
from typing import Any

from django.utils import timezone

from techbrief.apps.content_pipeline.models import (
    ContentItem,
    ContentStage,
    ContentStatus,
    DiscoveryRun,
    DiscoveryRunType,
    EndpointContentScope,
    EndpointRole,
    EndpointType,
    Source,
    SourceEndpoint,
    TriggeredBy,
)
from techbrief.apps.content_pipeline.services import ContentPipelineService, DiscoveryWorkflowService
from techbrief.apps.content_pipeline.tasks import load_replay_sample
from techbrief.apps.integrations.adapters import MockEmailAdapter, MockWeChatDraftAdapter
from techbrief.apps.publishers.models import (
    ContentPageSnapshot,
    EmailDelivery,
    PublishChannel,
    PublishRecord,
    Subscriber,
    SubscriberSourcePage,
    SubscriberStatus,
)
from techbrief.apps.publishers.services import create_wechat_draft, notify_content_item, publish_content_item

REPLAY_SAMPLES_DIR = Path(__file__).resolve().parent / "replay_samples"
DEFAULT_ACCEPTANCE_SUITE_NAME = "task11_acceptance_suite"


def load_acceptance_suite(suite_name: str = DEFAULT_ACCEPTANCE_SUITE_NAME) -> dict[str, Any]:
    suite_path = REPLAY_SAMPLES_DIR / f"{suite_name}.json"
    return json.loads(suite_path.read_text(encoding="utf-8"))


def analyze_markdown_structure(original_markdown: str | None, translated_markdown: str | None) -> dict[str, Any]:
    original_markdown = original_markdown or ""
    translated_markdown = translated_markdown or ""
    original_summary = _build_markdown_summary(original_markdown)
    translated_summary = _build_markdown_summary(translated_markdown)
    checks = {
        "heading_levels_match": original_summary["heading_levels"] == translated_summary["heading_levels"],
        "code_block_count_match": original_summary["code_block_count"] == translated_summary["code_block_count"],
        "link_targets_match": original_summary["link_targets"] == translated_summary["link_targets"],
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "original": original_summary,
        "translated": translated_summary,
    }


def run_acceptance_suite(suite_name: str = DEFAULT_ACCEPTANCE_SUITE_NAME) -> dict[str, Any]:
    suite = load_acceptance_suite(suite_name)
    executed_at = timezone.now().isoformat()

    review_scenarios = [
        _run_review_pending_scenario(sample_name)
        for sample_name in suite.get("review_pending_samples", [])
    ]
    publish_scenarios = [
        _run_publish_notify_scenario(sample_name)
        for sample_name in suite.get("publish_notify_samples", [])
    ]
    failure_scenarios = {
        "notify_partial_failure": _run_notify_partial_failure_scenario(
            suite["failure_injection_samples"]["notify_partial_failure"]
        ),
        "wechat_failure_non_blocking": _run_wechat_failure_non_blocking_scenario(
            suite["failure_injection_samples"]["wechat_failure_non_blocking"]
        ),
    }

    sources = sorted(
        {
            scenario["source_code"]
            for scenario in [*review_scenarios, *publish_scenarios]
        }
    )
    content_types = sorted(
        {
            scenario["content_type"]
            for scenario in [*review_scenarios, *publish_scenarios]
        }
    )

    criteria = [
        {
            "code": "replay_sources_covered",
            "status": _criterion_status({"openai", "anthropic"}.issubset(set(sources))),
            "details": {
                "sources": sources,
                "expected_sources": ["openai", "anthropic"],
            },
        },
        {
            "code": "replay_content_types_covered",
            "status": _criterion_status({"article", "video"}.issubset(set(content_types))),
            "details": {
                "content_types": content_types,
                "expected_content_types": ["article", "video"],
            },
        },
        {
            "code": "review_pending_chain_ready",
            "status": _criterion_status(
                bool(review_scenarios)
                and all(scenario["status"] == ContentStatus.REVIEW_PENDING for scenario in review_scenarios)
            ),
            "details": {
                "scenario_statuses": {
                    scenario["sample_name"]: scenario["status"] for scenario in review_scenarios
                }
            },
        },
        {
            "code": "publish_notify_chain_ready",
            "status": _criterion_status(
                bool(publish_scenarios)
                and all(scenario["status"] == ContentStatus.PUBLISHED for scenario in publish_scenarios)
                and all(scenario["notify"]["failed_count"] == 0 for scenario in publish_scenarios)
            ),
            "details": {
                "scenario_statuses": {
                    scenario["sample_name"]: {
                        "content_status": scenario["status"],
                        "notify_failed_count": scenario["notify"]["failed_count"],
                    }
                    for scenario in publish_scenarios
                }
            },
        },
        {
            "code": "structure_fidelity_checks_pass",
            "status": _criterion_status(
                all(scenario["structure_check"]["passed"] for scenario in [*review_scenarios, *publish_scenarios])
            ),
            "details": {
                "scenario_statuses": {
                    scenario["sample_name"]: scenario["structure_check"]["checks"]
                    for scenario in [*review_scenarios, *publish_scenarios]
                }
            },
        },
        {
            "code": "notify_failure_does_not_rollback_web_publish",
            "status": _criterion_status(
                failure_scenarios["notify_partial_failure"]["status"] == ContentStatus.PUBLISHED
                and failure_scenarios["notify_partial_failure"]["web_publish_record_exists"]
                and failure_scenarios["notify_partial_failure"]["notify"]["failed_count"] > 0
            ),
            "details": failure_scenarios["notify_partial_failure"],
        },
        {
            "code": "wechat_failure_does_not_block_web_publish",
            "status": _criterion_status(
                failure_scenarios["wechat_failure_non_blocking"]["status"] == ContentStatus.PUBLISHED
                and failure_scenarios["wechat_failure_non_blocking"]["web_publish_record_exists"]
                and failure_scenarios["wechat_failure_non_blocking"]["wechat"]["status"] == "failed"
            ),
            "details": failure_scenarios["wechat_failure_non_blocking"],
        },
    ]

    return {
        "suite_name": suite_name,
        "scope": "mock-first replay validation for Task11.1",
        "executed_at": executed_at,
        "coverage": {
            "review_pending_samples": [scenario["sample_name"] for scenario in review_scenarios],
            "publish_notify_samples": [scenario["sample_name"] for scenario in publish_scenarios],
            "sources": sources,
            "content_types": content_types,
        },
        "criteria": criteria,
        "limitations": list(suite.get("limitations", [])),
        "scenarios": {
            "review_pending": review_scenarios,
            "publish_notify": publish_scenarios,
            "failure_injection": failure_scenarios,
        },
    }


def _run_review_pending_scenario(sample_name: str) -> dict[str, Any]:
    sample = load_replay_sample(sample_name)
    source_data = sample["source"]
    endpoint_data = sample["endpoint"]
    source, _ = Source.objects.update_or_create(
        source_code=f"{source_data['source_code']}-review-{sample_name}",
        defaults={
            "source_name": source_data["source_name"],
            "base_url": source_data.get("base_url"),
            "default_language": source_data.get("default_language", "en"),
        },
    )
    endpoint, _ = SourceEndpoint.objects.update_or_create(
        source=source,
        endpoint_url=endpoint_data["endpoint_url"],
        defaults={
            "endpoint_type": endpoint_data.get("endpoint_type", EndpointType.RSS),
            "endpoint_role": endpoint_data.get("endpoint_role", EndpointRole.PRIMARY),
            "content_type_scope": endpoint_data.get("content_type_scope", EndpointContentScope.MIXED),
            "parser_config": {"mock_discovery_items": sample["discovery_items"]},
        },
    )
    discovery_run = DiscoveryRun.objects.create(
        run_type=DiscoveryRunType.REPLAY,
        status="queued",
        triggered_by=TriggeredBy.SYSTEM,
        source_scope={"source_codes": [source.source_code]},
    )
    discovery_result = DiscoveryWorkflowService.run(discovery_run.id)

    for content_item_id in discovery_result["content_item_ids"]:
        next_stage = ContentStage.FETCH
        while next_stage:
            result = ContentPipelineService.run_stage(
                content_item_id=content_item_id,
                stage=next_stage,
                run_id=discovery_result["run_id"],
                discovery_run_id=discovery_result["discovery_run_id"],
                triggered_by=TriggeredBy.SYSTEM,
            )
            next_stage = result["next_stage"]

    content_item = ContentItem.objects.get(dedupe_key=sample["discovery_items"][0]["dedupe_key"])
    structure_check = analyze_markdown_structure(content_item.content_md, content_item.zh_md)
    return {
        "sample_name": sample_name,
        "source_code": sample["source"]["source_code"],
        "content_type": content_item.content_type,
        "endpoint_url": endpoint.endpoint_url,
        "content_item_id": str(content_item.id),
        "status": content_item.status,
        "current_stage": content_item.current_stage,
        "structure_check": structure_check,
    }


def _run_publish_notify_scenario(sample_name: str) -> dict[str, Any]:
    result = _run_isolated_publish_replay(
        sample_name=sample_name,
        isolation_suffix="success",
        email_adapter=MockEmailAdapter(),
        wechat_adapter=MockWeChatDraftAdapter(),
    )
    sample = load_replay_sample(sample_name)
    content_item = ContentItem.objects.get(id=result["content_item_id"])
    return {
        "sample_name": sample_name,
        "source_code": sample["source"]["source_code"],
        "content_type": sample["content_item"]["content_type"],
        "content_item_id": str(content_item.id),
        "status": content_item.status,
        "notify": result["notify"],
        "wechat": result["wechat"],
        "structure_check": analyze_markdown_structure(content_item.content_md, content_item.zh_md),
    }


def _run_notify_partial_failure_scenario(sample_name: str) -> dict[str, Any]:
    sample = load_replay_sample(sample_name)
    failing_email = f"notify-failure-{sample['subscribers'][-1]['email']}"
    result = _run_isolated_publish_replay(
        sample_name=sample_name,
        isolation_suffix="notify-failure",
        email_adapter=MockEmailAdapter(fail_for={failing_email}),
        wechat_adapter=MockWeChatDraftAdapter(),
    )
    content_item = ContentItem.objects.get(id=result["content_item_id"])
    return {
        "sample_name": sample_name,
        "status": content_item.status,
        "notify": result["notify"],
        "web_publish_record_exists": PublishRecord.objects.filter(
            content_item=content_item,
            channel=PublishChannel.WEB,
            status="success",
        ).exists(),
        "published_snapshot_exists": ContentPageSnapshot.objects.filter(
            content_item=content_item,
            is_published=True,
        ).exists(),
        "failed_delivery_count": EmailDelivery.objects.filter(
            batch_id=result["notify"]["batch_id"],
            status="failed",
        ).count(),
    }


def _run_wechat_failure_non_blocking_scenario(sample_name: str) -> dict[str, Any]:
    result = _run_isolated_publish_replay(
        sample_name=sample_name,
        isolation_suffix="wechat-failure",
        email_adapter=MockEmailAdapter(),
        wechat_adapter=MockWeChatDraftAdapter(fail=True),
    )
    content_item = ContentItem.objects.get(id=result["content_item_id"])
    return {
        "sample_name": sample_name,
        "status": content_item.status,
        "notify": result["notify"],
        "wechat": result["wechat"],
        "web_publish_record_exists": PublishRecord.objects.filter(
            content_item=content_item,
            channel=PublishChannel.WEB,
            status="success",
        ).exists(),
        "published_snapshot_exists": ContentPageSnapshot.objects.filter(
            content_item=content_item,
            is_published=True,
        ).exists(),
    }


def _criterion_status(passed: bool) -> str:
    return "passed" if passed else "failed"


def _run_isolated_publish_replay(
    *,
    sample_name: str,
    isolation_suffix: str,
    email_adapter: MockEmailAdapter,
    wechat_adapter: MockWeChatDraftAdapter,
) -> dict[str, Any]:
    sample = deepcopy(load_replay_sample(sample_name))
    source_data = sample["source"]
    content_data = sample["content_item"]
    Subscriber.objects.all().delete()

    source, _ = Source.objects.update_or_create(
        source_code=f"{source_data['source_code']}-{isolation_suffix}",
        defaults={
            "source_name": source_data["source_name"],
            "base_url": source_data.get("base_url"),
        },
    )
    content_item, _ = ContentItem.objects.update_or_create(
        dedupe_key=f"{content_data['dedupe_key']}-{isolation_suffix}",
        defaults={
            "source": source,
            "source_name_snapshot": content_data["source_name_snapshot"],
            "content_type": content_data["content_type"],
            "ingestion_mode": content_data["ingestion_mode"],
            "status": content_data["status"],
            "current_stage": content_data["current_stage"],
            "title_original": content_data["title_original"],
            "title_zh": content_data.get("title_zh"),
            "summary_original": content_data.get("summary_original"),
            "summary_zh": content_data.get("summary_zh"),
            "author_or_speaker": content_data.get("author_or_speaker"),
            "source_url": content_data.get("source_url"),
            "canonical_url": content_data.get("canonical_url"),
            "content_md": content_data.get("content_md"),
            "zh_md": content_data.get("zh_md"),
            "supports_bilingual": content_data.get("supports_bilingual", True),
        },
    )

    created_subscribers: list[str] = []
    for subscriber_data in sample.get("subscribers", []):
        email = f"{isolation_suffix}-{subscriber_data['email']}"
        Subscriber.objects.create(
            email=email.lower(),
            status=subscriber_data.get("status", SubscriberStatus.ACTIVE),
            source_page=subscriber_data.get("source_page", SubscriberSourcePage.UNKNOWN),
            locale=subscriber_data.get("locale", "zh-CN"),
            unsubscribe_token=f"{subscriber_data['unsubscribe_token']}-{isolation_suffix}",
        )
        created_subscribers.append(email.lower())

    publish_result = publish_content_item(content_item)
    notify_result = notify_content_item(
        content_item,
        email_adapter=email_adapter,
        batch_date=date(2026, 6, 1 + (sum(ord(char) for char in isolation_suffix) % 20)),
    )
    wechat_result = create_wechat_draft(
        content_item=content_item,
        adapter=wechat_adapter,
    )
    return {
        "content_item_id": str(content_item.id),
        "publish": publish_result,
        "notify": notify_result,
        "wechat": wechat_result,
        "subscriber_emails": created_subscribers,
    }


def _build_markdown_summary(markdown_text: str) -> dict[str, Any]:
    heading_levels = [len(match.group(1)) for match in re.finditer(r"^(#{1,6})\s+", markdown_text, re.MULTILINE)]
    code_block_count = markdown_text.count("```") // 2
    link_targets = sorted({match.group(2) for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", markdown_text)})
    return {
        "heading_levels": heading_levels,
        "code_block_count": code_block_count,
        "link_targets": link_targets,
    }
