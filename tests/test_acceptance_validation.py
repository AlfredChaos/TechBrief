from __future__ import annotations

import json

import pytest
from django.core.management import call_command

from techbrief.apps.content_pipeline.validation import analyze_markdown_structure, run_acceptance_suite


def test_analyze_markdown_structure_detects_preserved_headings_code_and_links():
    report = analyze_markdown_structure(
        "# Title\n\n## Section\n\n```python\nprint('x')\n```\n\nRead [doc](https://example.com).",
        "# 标题\n\n## 章节\n\n```python\nprint('x')\n```\n\n阅读 [doc](https://example.com)。",
    )

    assert report["passed"] is True
    assert report["checks"]["heading_levels_match"] is True
    assert report["checks"]["code_block_count_match"] is True
    assert report["checks"]["link_targets_match"] is True


@pytest.mark.django_db
def test_run_acceptance_suite_reports_mock_first_coverage(settings):
    settings.PUBLIC_BASE_URL = "http://127.0.0.1:8010"

    report = run_acceptance_suite()
    criteria_by_code = {criterion["code"]: criterion for criterion in report["criteria"]}

    assert report["scope"] == "mock-first replay validation for Task11.1"
    assert report["coverage"]["sources"] == ["anthropic", "openai"]
    assert report["coverage"]["content_types"] == ["article", "video"]
    assert criteria_by_code["replay_sources_covered"]["status"] == "passed"
    assert criteria_by_code["replay_content_types_covered"]["status"] == "passed"
    assert criteria_by_code["review_pending_chain_ready"]["status"] == "passed"
    assert criteria_by_code["publish_notify_chain_ready"]["status"] == "passed"
    assert criteria_by_code["structure_fidelity_checks_pass"]["status"] == "passed"
    assert criteria_by_code["notify_failure_does_not_rollback_web_publish"]["status"] == "passed"
    assert criteria_by_code["wechat_failure_does_not_block_web_publish"]["status"] == "passed"
    assert "does not claim 10/10 historical replay acceptance" in report["limitations"][0]


@pytest.mark.django_db
def test_validate_acceptance_replays_command_writes_report(tmp_path, settings):
    settings.PUBLIC_BASE_URL = "http://127.0.0.1:8010"
    report_file = tmp_path / "task11-report.json"

    call_command("validate_acceptance_replays", report_file=str(report_file))

    payload = json.loads(report_file.read_text(encoding="utf-8"))
    assert payload["suite_name"] == "task11_acceptance_suite"
    assert payload["criteria"]
