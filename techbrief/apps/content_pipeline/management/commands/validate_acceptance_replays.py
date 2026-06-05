from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand

from techbrief.apps.content_pipeline.validation import (
    DEFAULT_ACCEPTANCE_SUITE_NAME,
    run_acceptance_suite,
)


class Command(BaseCommand):
    help = "Run Task11.1 mock-first acceptance replays and print a structured report."

    def add_arguments(self, parser):
        parser.add_argument(
            "--suite",
            default=DEFAULT_ACCEPTANCE_SUITE_NAME,
            help="Acceptance replay suite name under techbrief/apps/content_pipeline/replay_samples.",
        )
        parser.add_argument(
            "--report-file",
            default="",
            help="Optional path to write the JSON report.",
        )

    def handle(self, *args, **options):
        report = run_acceptance_suite(options["suite"])
        if options["report_file"]:
            report_path = Path(options["report_file"]).expanduser().resolve()
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Wrote acceptance replay report: {report_path}"))

        passed_count = sum(1 for item in report["criteria"] if item["status"] == "passed")
        total_count = len(report["criteria"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Acceptance replay suite '{report['suite_name']}' finished: {passed_count}/{total_count} criteria passed."
            )
        )
        for criterion in report["criteria"]:
            status = "PASS" if criterion["status"] == "passed" else "FAIL"
            self.stdout.write(f"[{status}] {criterion['code']}")
