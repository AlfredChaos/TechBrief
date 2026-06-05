from __future__ import annotations

import json

import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_generate_task11_evidence_writes_report_and_samples(tmp_path, settings):
    settings.PUBLIC_BASE_URL = "http://127.0.0.1:8010"
    settings.ADMIN_BASE_URL = "http://127.0.0.1:8010"

    output_dir = tmp_path / "task11-evidence"

    call_command("generate_task11_evidence", output_dir=str(output_dir))
    call_command("generate_task11_evidence", output_dir=str(output_dir))

    report = json.loads((output_dir / "report.json").read_text())
    summary = (output_dir / "summary.md").read_text()

    assert report["flows"]["public_site"]["routes"]["home"]["status_code"] == 200
    assert report["flows"]["public_site"]["subscription"]["subscriber_status"] == "unsubscribed"
    assert report["flows"]["admin_console"]["pages"]["dashboard"]["status_code"] == 200
    assert report["flows"]["pipeline"]["discovery_result"]["discovered_count"] == 1
    assert report["flows"]["publish_notify_wechat"]["digest_batch"]["status"] == "sent"

    assert "Task 11 验收验证与证据汇总" in summary
    assert (output_dir / "samples" / "public-home.html").exists()
    assert (output_dir / "samples" / "admin-dashboard.json").exists()
    assert (output_dir / "samples" / "pipeline-run-logs.json").exists()
    assert (output_dir / "samples" / "publish-notify-wechat.json").exists()
