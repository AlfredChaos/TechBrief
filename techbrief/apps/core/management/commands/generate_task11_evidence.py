from __future__ import annotations

import json
import uuid
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.core.serializers.json import DjangoJSONEncoder
from django.test import Client
from django.utils import timezone

from techbrief.apps.content_pipeline.models import (
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
from techbrief.apps.content_pipeline.tasks import replay_publish_notify_sample, run_discovery
from techbrief.apps.core.models import User
from techbrief.apps.integrations.adapters import MockEmailAdapter, MockWeChatDraftAdapter
from techbrief.apps.observability.models import RunLog
from techbrief.apps.publishers.models import (
    ContentPageSnapshot,
    EmailDelivery,
    EmailDigestBatch,
    PageKind,
    PublishRecord,
    Subscriber,
    SubscriberSourcePage,
    SubscriberStatus,
)


DEFAULT_OUTPUT_DIR = Path("docs/validation/task11")


class Command(BaseCommand):
    help = "Run Task 11 smoke validations and write reproducible evidence artifacts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            default=str(DEFAULT_OUTPUT_DIR),
            help="Directory used to write Task 11 validation evidence files.",
        )

    def handle(self, *args, **options):
        output_dir = Path(options["output_dir"]).expanduser()
        if not output_dir.is_absolute():
            output_dir = Path(settings.BASE_DIR) / output_dir
        samples_dir = output_dir / "samples"
        samples_dir.mkdir(parents=True, exist_ok=True)

        call_command("load_site_seed")
        admin_user = self._ensure_admin_user()
        self._seed_public_content()
        self._seed_admin_console_data(admin_user)

        public_client = Client()
        admin_client = Client()
        public_client.defaults["HTTP_HOST"] = self._resolve_host(settings.PUBLIC_BASE_URL)
        admin_client.defaults["HTTP_HOST"] = self._resolve_host(settings.ADMIN_BASE_URL)
        admin_client.force_login(admin_user)

        public_results = self._collect_public_site_evidence(public_client, samples_dir)
        admin_results = self._collect_admin_evidence(admin_client, samples_dir)
        pipeline_results = self._collect_pipeline_evidence(samples_dir)
        publish_results = self._collect_publish_evidence(samples_dir)

        report = {
            "generated_at": timezone.now().isoformat(),
            "command": "python manage.py generate_task11_evidence",
            "settings_module": settings.SETTINGS_MODULE if hasattr(settings, "SETTINGS_MODULE") else None,
            "base_urls": {
                "public": settings.PUBLIC_BASE_URL,
                "admin": settings.ADMIN_BASE_URL,
            },
            "flows": {
                "public_site": public_results,
                "admin_console": admin_results,
                "pipeline": pipeline_results,
                "publish_notify_wechat": publish_results,
            },
            "limitations": [
                "Email and WeChat checks use mock adapters in this validation run.",
                "COS, ASR, and GA4 real integrations are not exercised by this command.",
                "Browser screenshots are not captured in the current CLI environment.",
            ],
        }
        self._write_json(output_dir / "report.json", report)
        self._write_summary(output_dir / "summary.md", report)
        self.stdout.write(self.style.SUCCESS(f"Task 11 evidence written to {output_dir}"))

    def _ensure_admin_user(self) -> User:
        user, _ = User.objects.get_or_create(
            username="task11-operator",
            defaults={
                "email": "task11-operator@example.com",
                "display_name": "Task11 Operator",
                "is_staff": True,
                "is_superuser": True,
                "is_platform_admin": True,
                "is_active": True,
            },
        )
        user.email = "task11-operator@example.com"
        user.display_name = "Task11 Operator"
        user.is_staff = True
        user.is_superuser = True
        user.is_platform_admin = True
        user.is_active = True
        user.set_password("task11-secret-123")
        user.save()
        return user

    def _seed_public_content(self) -> None:
        source, _ = Source.objects.get_or_create(
            source_code="task11-openai",
            defaults={
                "source_name": "OpenAI",
                "base_url": "https://openai.com",
            },
        )
        published_at = timezone.now()
        article, _ = ContentItem.objects.update_or_create(
            dedupe_key="task11-public-article".ljust(64, "a"),
            defaults={
                "source": source,
                "source_name_snapshot": "OpenAI",
                "content_type": ContentType.ARTICLE,
                "status": ContentStatus.PUBLISHED,
                "current_stage": ContentStage.NOTIFY,
                "title_original": "Task11 OpenAI Reasoning Models",
                "title_zh": "Task11 OpenAI 推理模型",
                "summary_original": "Task11 public article summary.",
                "summary_zh": "Task11 公开文章摘要。",
                "author_or_speaker": "OpenAI",
                "source_url": "https://openai.com/research/task11-reasoning",
                "canonical_url": "https://openai.com/research/task11-reasoning",
                "dedupe_key": "task11-public-article".ljust(64, "a"),
                "published_at_source": published_at,
                "published_at_web": published_at,
                "supports_bilingual": True,
                "web_slug": "task11-openai-reasoning-models",
                "content_md": "## How it works\n\nTask11 original body.",
                "zh_md": "## 工作原理\n\nTask11 中文正文。",
            },
        )
        ContentPageSnapshot.objects.update_or_create(
            content_item=article,
            defaults={
                "page_kind": PageKind.ARTICLE,
                "slug": "task11-openai-reasoning-models",
                "source_name_snapshot": "OpenAI",
                "title_original_snapshot": "Task11 OpenAI Reasoning Models",
                "title_zh_snapshot": "Task11 OpenAI 推理模型",
                "summary_zh_snapshot": "Task11 公开文章摘要。",
                "body_original_md_snapshot": "## How it works\n\nTask11 original body.",
                "body_zh_md_snapshot": "## 工作原理\n\nTask11 中文正文。",
                "author_or_speaker_snapshot": "OpenAI",
                "source_url_snapshot": "https://openai.com/research/task11-reasoning",
                "canonical_url_snapshot": "https://openai.com/research/task11-reasoning",
                "published_at_source_snapshot": published_at,
                "supports_bilingual": True,
                "disclaimer_md_snapshot": "This is a translated editorial briefing.",
                "is_published": True,
                "published_at": published_at,
                "last_synced_at": published_at,
            },
        )

    def _seed_admin_console_data(self, admin_user: User) -> None:
        source, _ = Source.objects.get_or_create(
            source_code="task11-admin-source",
            defaults={
                "source_name": "Anthropic",
                "base_url": "https://anthropic.com",
            },
        )
        now = timezone.now()
        review_content, _ = ContentItem.objects.update_or_create(
            dedupe_key="task11-admin-review".ljust(64, "b"),
            defaults={
                "source": source,
                "source_name_snapshot": "Anthropic",
                "content_type": ContentType.ARTICLE,
                "status": ContentStatus.REVIEW_PENDING,
                "current_stage": ContentStage.REVIEW_PENDING,
                "title_original": "Task11 Review Pending Article",
                "title_zh": "Task11 待审核文章",
                "dedupe_key": "task11-admin-review".ljust(64, "b"),
                "published_at_source": now,
                "last_processed_at": now,
                "web_slug": "task11-review-pending-article",
            },
        )
        ContentItem.objects.update_or_create(
            dedupe_key="task11-admin-failed".ljust(64, "c"),
            defaults={
                "source": source,
                "source_name_snapshot": "Anthropic",
                "content_type": ContentType.VIDEO,
                "status": ContentStatus.FAILED,
                "current_stage": ContentStage.TRANSLATE,
                "title_original": "Task11 Failed Video",
                "title_zh": "Task11 失败视频",
                "dedupe_key": "task11-admin-failed".ljust(64, "c"),
                "published_at_source": now,
                "last_error_code": "TRANSLATE_TIMEOUT",
                "last_error_stage": ContentStage.TRANSLATE,
            },
        )
        Subscriber.objects.update_or_create(
            email="task11-active@example.com",
            defaults={
                "status": SubscriberStatus.ACTIVE,
                "source_page": SubscriberSourcePage.HOME_HERO,
                "locale": "zh-CN",
                "unsubscribe_token": "task11-active-token",
                "last_sent_at": now,
            },
        )
        Subscriber.objects.update_or_create(
            email="task11-unsubscribed@example.com",
            defaults={
                "status": SubscriberStatus.UNSUBSCRIBED,
                "source_page": SubscriberSourcePage.NAV_MODAL,
                "locale": "zh-CN",
                "unsubscribe_token": "task11-unsubscribed-token",
                "unsubscribed_at": now,
            },
        )
        run_id = uuid.uuid5(uuid.NAMESPACE_DNS, "techbrief-task11-admin-workflow")
        RunLog.objects.update_or_create(
            run_id=run_id,
            content_item=review_content,
            stage=ContentStage.FETCH,
            defaults={
                "status": "success",
                "triggered_by": TriggeredBy.ADMIN_USER,
                "triggered_by_user": admin_user,
                "started_at": now,
                "ended_at": now,
                "duration_ms": 1200,
            },
        )
        RunLog.objects.update_or_create(
            run_id=run_id,
            content_item=review_content,
            stage=ContentStage.TRANSLATE,
            defaults={
                "status": "failed",
                "triggered_by": TriggeredBy.ADMIN_USER,
                "triggered_by_user": admin_user,
                "started_at": now,
                "ended_at": now,
                "duration_ms": 3200,
                "error_code": "TRANSLATE_TIMEOUT",
                "error_summary": "Task11 simulated translate timeout.",
                "retryable": True,
            },
        )

    def _collect_public_site_evidence(self, client: Client, samples_dir: Path) -> dict:
        run_token = uuid.uuid4().hex[:8]
        subscriber_email = f"task11-reader-{run_token}@example.com"
        idempotency_key = f"task11-subscribe-{run_token}"
        home = client.get("/", HTTP_ACCEPT_LANGUAGE="zh-CN")
        articles = client.get(
            "/articles?source=task11-openai&content_type=article",
            HTTP_ACCEPT_LANGUAGE="zh-CN",
        )
        archive = client.get("/archive", HTTP_ACCEPT_LANGUAGE="zh-CN")
        detail = client.get(
            "/articles/task11-openai-reasoning-models?view=bilingual",
            HTTP_ACCEPT_LANGUAGE="zh-CN",
        )
        about = client.get("/about", HTTP_ACCEPT_LANGUAGE="zh-CN")
        privacy = client.get("/privacy", HTTP_ACCEPT_LANGUAGE="zh-CN")
        terms = client.get("/terms", HTTP_ACCEPT_LANGUAGE="zh-CN")
        api_list = client.get(
            "/api/public/content-items?source=task11-openai&content_type=article",
            HTTP_ACCEPT_LANGUAGE="zh-CN",
        )
        api_detail = client.get(
            "/api/public/content-items/task11-openai-reasoning-models?view=bilingual",
            HTTP_ACCEPT_LANGUAGE="en-US",
        )
        subscribe = client.post(
            "/api/public/subscriptions",
            data=json.dumps(
                {
                    "email": subscriber_email,
                    "source_page": "home_hero",
                    "locale": "zh-CN",
                }
            ),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )
        subscribe_repeat = client.post(
            "/api/public/subscriptions",
            data=json.dumps(
                {
                    "email": subscriber_email,
                    "source_page": "home_hero",
                    "locale": "zh-CN",
                }
            ),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )
        if subscribe.status_code != 200:
            raise RuntimeError(f"subscription create failed: {subscribe.status_code} {subscribe.content.decode()}")
        if subscribe_repeat.status_code != 200:
            raise RuntimeError(
                f"subscription replay failed: {subscribe_repeat.status_code} {subscribe_repeat.content.decode()}"
            )
        subscriber = Subscriber.objects.get(email=subscriber_email)
        unsubscribe = client.post(
            "/api/public/subscriptions/unsubscribe",
            data=json.dumps({"token": subscriber.unsubscribe_token}),
            content_type="application/json",
        )
        unsubscribe_page = client.get(f"/unsubscribe/{subscriber.unsubscribe_token}", HTTP_ACCEPT_LANGUAGE="zh-CN")

        self._write_text(samples_dir / "public-home.html", home.content.decode())
        self._write_text(samples_dir / "public-articles.html", articles.content.decode())
        self._write_text(samples_dir / "public-archive.html", archive.content.decode())
        self._write_text(samples_dir / "public-article-detail.html", detail.content.decode())
        self._write_json(samples_dir / "public-content-items.json", api_list.json())
        self._write_json(samples_dir / "public-content-item-detail.json", api_detail.json())
        self._write_json(samples_dir / "subscription-create.json", subscribe.json())
        self._write_json(samples_dir / "subscription-unsubscribe.json", unsubscribe.json())

        return {
            "routes": {
                "home": {"status_code": home.status_code, "contains_title": "Task11 OpenAI 推理模型" in home.content.decode()},
                "articles": {"status_code": articles.status_code, "filtered": "Task11 OpenAI 推理模型" in articles.content.decode()},
                "archive": {"status_code": archive.status_code},
                "detail": {
                    "status_code": detail.status_code,
                    "contains_zh": "工作原理" in detail.content.decode(),
                    "contains_original": "How it works" in detail.content.decode(),
                },
                "about": {"status_code": about.status_code},
                "privacy": {"status_code": privacy.status_code},
                "terms": {"status_code": terms.status_code},
                "unsubscribe_page": {
                    "status_code": unsubscribe_page.status_code,
                    "contains_success_message": "退订已生效" in unsubscribe_page.content.decode(),
                },
            },
            "apis": {
                "content_items": api_list.json(),
                "content_item_detail": api_detail.json(),
            },
            "subscription": {
                "create": subscribe.json(),
                "repeat_same_idempotency_key": subscribe_repeat.json(),
                "unsubscribe": unsubscribe.json(),
                "subscriber_email": subscriber_email,
                "subscriber_status": Subscriber.objects.get(email=subscriber_email).status,
                "unsubscribe_token": subscriber.unsubscribe_token,
            },
        }

    def _collect_admin_evidence(self, client: Client, samples_dir: Path) -> dict:
        dashboard = client.get("/cms/techbrief/")
        content = client.get("/cms/techbrief/content/?q=Task11")
        subscribers = client.get("/cms/techbrief/subscribers/?status=unsubscribed")
        workflow = client.get("/cms/techbrief/workflow/?status=failed")
        api_dashboard = client.get("/cms/techbrief/api/dashboard/")
        api_content = client.get("/cms/techbrief/api/content-items/?q=Task11&status=review_pending")
        api_subscribers = client.get("/cms/techbrief/api/subscribers/?status=unsubscribed")
        api_workflow = client.get("/cms/techbrief/api/workflow/runs/?status=failed")

        self._write_text(samples_dir / "admin-dashboard.html", dashboard.content.decode())
        self._write_json(samples_dir / "admin-dashboard.json", api_dashboard.json())
        self._write_json(samples_dir / "admin-content.json", api_content.json())
        self._write_json(samples_dir / "admin-subscribers.json", api_subscribers.json())
        self._write_json(samples_dir / "admin-workflow.json", api_workflow.json())

        return {
            "pages": {
                "dashboard": {"status_code": dashboard.status_code},
                "content": {"status_code": content.status_code},
                "subscribers": {"status_code": subscribers.status_code},
                "workflow": {"status_code": workflow.status_code},
            },
            "apis": {
                "dashboard": api_dashboard.json(),
                "content": api_content.json(),
                "subscribers": api_subscribers.json(),
                "workflow": api_workflow.json(),
            },
        }

    def _collect_pipeline_evidence(self, samples_dir: Path) -> dict:
        source, _ = Source.objects.get_or_create(
            source_code="task11-pipeline-source",
            defaults={
                "source_name": "Pipeline Source",
                "base_url": "https://example.com",
            },
        )
        endpoint, _ = SourceEndpoint.objects.update_or_create(
            source=source,
            endpoint_url="https://example.com/task11/rss.xml",
            defaults={
                "endpoint_type": EndpointType.RSS,
                "endpoint_role": EndpointRole.PRIMARY,
                "content_type_scope": EndpointContentScope.ARTICLE,
                "parser_config": {
                    "mock_discovery_items": [
                        {
                            "title_original": "Task11 Pipeline Article",
                            "summary_original": "Task11 pipeline replay article.",
                            "source_url": "https://example.com/task11/article",
                            "canonical_url": "https://example.com/task11/article",
                            "source_item_id": "task11-pipeline-article",
                            "published_at_source": timezone.now().isoformat(),
                            "content_type": ContentType.ARTICLE,
                        }
                    ]
                },
            },
        )
        discovery_run = DiscoveryRun.objects.create(
            run_type=DiscoveryRunType.REPLAY,
            status=DiscoveryRunStatus.QUEUED,
            triggered_by=TriggeredBy.SYSTEM,
            source_scope={"source_code": source.source_code, "endpoint_id": str(endpoint.id)},
        )
        result = run_discovery(discovery_run_id=str(discovery_run.id))
        run_logs = list(
            RunLog.objects.filter(run_id=result["run_id"]).order_by("created_at", "stage").values(
                "stage",
                "status",
                "retryable",
                "error_code",
                "context_json",
            )
        )
        self._write_json(samples_dir / "pipeline-discovery.json", result)
        self._write_json(samples_dir / "pipeline-run-logs.json", run_logs)
        return {
            "discovery_result": result,
            "run_logs": run_logs,
            "content_item_ids": result["content_item_ids"],
        }

    def _collect_publish_evidence(self, samples_dir: Path) -> dict:
        result = replay_publish_notify_sample(
            email_adapter=MockEmailAdapter(),
            wechat_adapter=MockWeChatDraftAdapter(),
        )
        run_logs = list(
            RunLog.objects.filter(run_id=result["run_id"]).order_by("created_at", "stage").values(
                "stage",
                "status",
                "retryable",
                "error_code",
                "context_json",
            )
        )
        publish_records = list(
            PublishRecord.objects.filter(run_id=result["run_id"]).order_by("channel", "created_at").values(
                "channel",
                "status",
                "external_id",
                "error_code",
                "response_snapshot",
            )
        )
        deliveries = list(
            EmailDelivery.objects.filter(batch_id=result["notify"]["batch_id"]).order_by("subscriber__email").values(
                "subscriber__email",
                "status",
                "provider_message_id",
                "error_code",
            )
        )
        snapshot = ContentPageSnapshot.objects.get(content_item_id=result["content_item_id"])
        batch = EmailDigestBatch.objects.get(id=result["notify"]["batch_id"])

        evidence = {
            "result": result,
            "snapshot": {
                "snapshot_id": str(snapshot.id),
                "slug": snapshot.slug,
                "is_published": snapshot.is_published,
            },
            "digest_batch": {
                "batch_id": str(batch.id),
                "status": batch.status,
                "sent_count": batch.sent_count,
                "failed_count": batch.failed_count,
            },
            "publish_records": publish_records,
            "deliveries": deliveries,
            "run_logs": run_logs,
        }
        self._write_json(samples_dir / "publish-notify-wechat.json", evidence)
        return evidence

    def _write_summary(self, path: Path, report: dict) -> None:
        files = sorted(str(file.relative_to(path.parent)) for file in path.parent.rglob("*") if file.is_file())
        lines = [
            "# Task 11 验收验证与证据汇总",
            "",
            f"- 生成时间: {report['generated_at']}",
            f"- 执行命令: `{report['command']} --settings=techbrief.settings.test`",
            f"- Public Base URL: `{report['base_urls']['public']}`",
            f"- Admin Base URL: `{report['base_urls']['admin']}`",
            "",
            "## 已验证链路",
            "",
            "- 公开站点: 首页、列表页、Archive、详情页、About、Privacy、Terms、退订结果页。",
            "- 订阅链路: 订阅、同幂等键重放、退订 API 与退订结果页。",
            "- 后台链路: 登录后仪表盘、内容列表、订阅者列表、工作流页及对应 API。",
            "- 流水线链路: `discover -> fetch -> extract -> transcribe -> translate -> research -> review_pending` mock 回放。",
            "- 发布链路: Web 发布、digest 邮件发送、微信草稿创建 mock 回放。",
            "- 运行证据: HTML 样本、API 返回、run log 摘要、发布记录、digest 投递记录。",
            "",
            "## 未覆盖或受限项",
            "",
            "- 当前命令未执行 Resend、微信、COS、ASR、GA4 的真实外部联调。",
            "- 当前环境未集成浏览器截图能力，因此未产出新的页面截图。",
            "- 当前证据以 mock 适配器与本地测试设置为主，用于回归验证与验收留痕，不等同于上线联调完成。",
            "",
            "## 证据文件",
            "",
        ]
        lines.extend(f"- `{file}`" for file in files)
        self._write_text(path, "\n".join(lines) + "\n")

    def _write_json(self, path: Path, payload) -> None:
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, cls=DjangoJSONEncoder) + "\n",
            encoding="utf-8",
        )

    def _write_text(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")

    def _resolve_host(self, base_url: str) -> str:
        parsed = urlparse(base_url)
        return parsed.hostname or "127.0.0.1"
