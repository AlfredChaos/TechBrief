# Tasks
- [x] Task 1: 完成实施前文档基线确认（当前建议状态：文档审计、外部补研、内部阻塞记录与 Phase 0 门禁已完成）
  - [x] SubTask 1.1: 逐份确认 README、PRD、技术方案、系统架构、数据库设计、API 设计、交付说明、验收清单已纳入阅读清单
  - [x] SubTask 1.2: 输出统一的需求优先级、冲突裁决规则和待确认缺口清单
  - [x] SubTask 1.3: 对可外部补足的信息缺口执行联网/MCP 补充调研，并沉淀事实依据
  - [x] SubTask 1.4: 将仍未闭合的内部前置缺口整理为阻塞清单，并明确其需要产品或资源 owner 决策
  - [x] SubTask 1.5: 将上述内部前置缺口纳入 Phase 0 / 实施启动门禁，并明确启动前仍需关闭或获得豁免
  - Evidence: `README.md` 已提供正式文档导航；`docs/delivery/Delivery-Guide.md` 已列出目标交付物；`docs/delivery/Database-Design.md` 与 `docs/delivery/API-Design.md` 已明确以 PRD、技术方案和 `stitch_ai_insight_bridge` 为输入
  - External Evidence: Google 官方文档已确认 GA4 需要 property、web data stream 与 Google tag，且 `page_view` 默认自动采集；Resend 官方文档已确认发送前需完成域名校验、DNS 记录配置与 API Key 创建，且校验通过后可直接从该域任意地址发信；腾讯云 COS 官方文档已确认落地前需 bucket、region、`SecretId`、`SecretKey`，并支持 `https` 协议；微信服务号官方文档已确认存在 `/cgi-bin/draft/add`、`/cgi-bin/draft/batchget` 等草稿箱接口，且 `access_token` 有效期 7200 秒、应由中控统一刷新；yt-dlp 官方 `supportedsites.md` 已证明技术上可覆盖大量公开视频站点，但也明确“是否可用仍需逐站点实测”； MiMo 官方文档已确认 `mimo-v2.5` 支持公网音频 URL 与 Base64 两种输入，其中单音频文件 URL 方式上限 100 MB、Base64 方式上限 50 MB
  - Priority: 正式裁决链固定为 `TechBrief-PRD.md -> docs/delivery/Technical-Solution-Report.md -> docs/delivery/Database-Design.md -> docs/delivery/API-Design.md -> docs/delivery/Acceptance-Checklist.md -> stitch_ai_insight_bridge/*`；`README.md` 仅作为导航索引
  - Resolved Research Gaps: 可由外部公开资料补足的事实缺口已通过补充调研闭合，不再作为未决阻塞项
  - Recorded Internal-Only Blockers: PRD 仍为“草案（待评审）”；公开域名、后台域名、DNS、HTTPS、GA4、COS、Resend、微信等资源与凭据由谁提供/谁持有未确认；“更多公开视频平台”首批白名单未锁定；视频时长上限与“无字幕视频是否全部转录或按优先级转录”未锁定；研究报告是否允许站内公开未锁定；初始管理员账号是否允许后续在后台修改用户名/密码未锁定
  - Phase 0 Gate: 上述内部缺口当前均已转化为 Phase 0 / 实施启动门禁；Task 1 的完成标准是“阻塞项已被如实记录并挂入门禁”，不是“阻塞项已全部闭合”

- [x] Task 2: 锁定 MVP 能力域与范围边界（当前建议状态：文档基线已锁定）
  - [x] SubTask 2.1: 将需求拆分为公开站点、后台管理、内容流水线、邮件订阅、微信草稿五个能力域
  - [x] SubTask 2.2: 固化 P0 页面、接口、数据对象、状态机和外部集成范围
  - [x] SubTask 2.3: 明确非目标与降级策略，避免开发阶段范围漂移
  - Evidence: 五大能力域已在 `TechBrief-PRD.md`、`docs/delivery/Delivery-Guide.md` 与 `spec.md` 中一致出现；P0 页面、接口分区、核心对象、状态链路与外部集成已分别在 PRD、技术方案、系统架构、数据库设计、API 设计、验收清单中落档
  - Boundaries: MVP 明确包含公开站点、后台管理、内容发现与处理、每日汇总邮件、后台微信草稿工具；明确排除评论、点赞、用户投稿、复杂 RBAC、多语言内容生产、全自动公众号发布
  - Recommendation: Task 2 可按“范围边界文档已锁定”判定完成，但进入 Task 5 之前仍应先关闭 Task 1 的剩余内部阻塞项或获得产品豁免

- [x] Task 3: 锁定前端保真实现基线
  - [x] SubTask 3.1: 将 `stitch_ai_insight_bridge` 中的 DESIGN、3 个公开 HTML 原型和 5 个后台截图映射为页面、组件、状态清单，并标注每项的来源素材与优先级
  - [x] SubTask 3.2: 补齐原型未覆盖页面规格，至少包括文章列表页、Archive、About、Privacy、Terms、退订确认页、退订成功页
  - [x] SubTask 3.3: 补齐关键缺失状态规格，至少包括订阅邮箱无效、提交中、失败、重复订阅、公开页空态/404/无结果态、详情页缺少译文或封面时的降级态、后台加载/空数据/错误/确认/反馈态
  - [x] SubTask 3.4: 固化视觉 token、响应式断点、主题模式、双语阅读模式、后台信息架构约束，并为首页、详情页、订阅弹窗、5 个后台页面分别建立可核对的验收条目
  - Deliverables: `spec.md` 已补充 Task 3 页面 / 组件 / 状态映射基线、缺失页面显式规格、共享组件映射基线、状态映射基线、缺失状态显式规格和前端验收矩阵；`checklist.md` 已新增对应可勾选验收项
  - Completion Evidence: 缺失页面规格已覆盖列表页、Archive、About、Privacy、Terms、退订确认页、退订成功页；缺失状态规格已覆盖订阅异常 / 处理中 / 重复订阅、公开页空态 / 无结果 / 404、详情页降级态、后台加载 / 空数据 / 错误 / 确认 / 反馈态
  - Recommendation: Task 3 现可按“前端保真实现基线已锁定”判定完成；后续 Task 5-6 应直接以 `spec.md` 与 `checklist.md` 为验收依据

- [x] Task 4: 锁定数据模型、接口与工作流边界（当前建议状态：文档边界基线已锁定）
  - [x] SubTask 4.1: 以数据库设计文档为基线，在 `spec.md` 锁定 `tb_source`、`tb_source_endpoint`、`tb_discovery_run`、`tb_discovery_run_source_stat`、`tb_content_item`、`tb_content_artifact`、`tb_run_log`、`tb_subscriber`、`tb_email_digest_batch`、`tb_email_delivery`、`tb_publish_record`、`tb_wechat_draft_detail`、`tb_content_page_snapshot` 及页面配置表的职责、关系和落库边界
  - [x] SubTask 4.2: 在 `spec.md` 明确 PostgreSQL 与 COS 的分层边界，以及 `dedupe_key`、`web_slug`、`unsubscribe_token`、`provider_message_id`、`wechat_draft_id` 等关键唯一键或外部关联键的归属位置
  - [x] SubTask 4.3: 以 API 设计文档为基线，在 `spec.md` 确认 `/api/public/*`、`/api/admin/*`、`/api/integrations/*` 的接口分区、认证方式、CSRF 要求、幂等性要求与统一错误码
  - [x] SubTask 4.4: 在 `spec.md` 固化 `discover -> fetch -> extract -> transcribe -> translate -> research -> review_pending -> publish -> notify` 的阶段输入、输出、状态写回位置、产物归属和主追踪对象
  - [x] SubTask 4.5: 在 `spec.md` 明确可重试阶段仅包括 `fetch`、`extract`、`transcribe`、`translate`、`research`、`publish`、`notify`，并固化“通知失败不回滚 Web 发布、微信草稿失败不阻断主站发布”的恢复边界
  - [x] SubTask 4.6: 在 `spec.md` 锁定 Source Adapters、Extractors、Media/ASR、LLM、COS、Resend、WeChat、GA4 的责任边界、调用方向和失败记录要求
  - Deliverable: 在 `spec.md` 输出 Task4 Boundary Matrix、Retry And Recovery Matrix、Integration Responsibility Matrix 三张矩阵，作为 Django/Wagtail、Celery 与外部适配器的实现边界基线
  - Completion Criteria: 所有表职责、对象存储边界、接口分区、幂等入口、主追踪对象、可重试阶段、失败不回滚规则、外部集成责任边界均已能从矩阵逐项核对
  - Recommendation: Task 4 可按“文档边界基线已锁定”判定完成；后续实现与验收应以该基线为准，若正式设计变更需同步回写矩阵

- [x] Task 5: 规划工程初始化与实现顺序（当前建议状态：开发路线文档已定义）
  - [x] SubTask 5.1: 在 `spec.md` 定义 Phase 0-7 的工程初始化与开发推进顺序
  - [x] SubTask 5.2: 在 `spec.md` 为各阶段明确最小交付物、退出检查和前置依赖
  - [x] SubTask 5.3: 在 `spec.md` 明确 Phase 0 受 Task 1 内部阻塞闭合或豁免约束，区分“路线已定义”与“可开始实施”
  - Deliverable: 在 `spec.md` 输出 Phase 0-7 的 Implementation Order 表和 Stage Deliverables 表，明确每阶段目标、最小交付物和退出检查
  - Completion Criteria: 每个阶段均具备可演示结果、验证动作和明确的前置条件，且 Phase 0 明确要求关闭 Task 1 缺口或获得豁免
  - Recommendation: Task 5 可按“开发路线已定义”判定完成，但这不代表工程已启动；Phase 1 实施启动仍受 Task 1 剩余内部阻塞项约束

- [x] Task 6: 建立验收映射与验证方案（当前建议状态：验收映射文档已建立）
  - [x] SubTask 6.1: 在 `spec.md` 将 PRD P0 与验收清单逐项映射到实现任务和验证动作
  - [x] SubTask 6.2: 在 `spec.md` 规划回放样本、结构保真检查、订阅链路验证、后台验证和外部集成验证
  - [x] SubTask 6.3: 在 `spec.md` 明确哪些检查需要 mock，哪些需要真实联调，哪些属于上线前阻断项
  - Deliverable: 在 `spec.md` 输出 Requirement-To-Validation Mapping 与 Validation Mode Matrix，覆盖页面、订阅、后台、流水线、发布、邮件、微信、日志、GA4
  - Completion Criteria: 每项 P0 能力均能映射到实现锚点、验证动作、验证环境、证据载体和上线阻断级别
  - Recommendation: Task 6 可按“验收映射文档已建立”判定完成，但外部集成项仍需在上线前补做真实联调验证

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 1
- Task 4 depends on Task 1
- Task 5 depends on Task 2
- Task 5 depends on Task 3
- Task 5 depends on Task 4
- Task 6 depends on Task 2
- Task 6 depends on Task 3
- Task 6 depends on Task 4
- Task 5 implementation start remains gated by unresolved internal-only blockers in Task 1 unless product explicitly waives them

# Implementation Tasks
- [x] Task 7: 完成 Phase 1 工程基座初始化
  - [x] SubTask 7.1: 初始化 Django + Wagtail + Celery 工程骨架与基础目录
  - [x] SubTask 7.2: 落地 `pyproject.toml`、依赖锁定、settings 分层与 `.env.example`
  - [x] SubTask 7.3: 接入 PostgreSQL、Redis、Celery beat、COS 基础配置与健康检查
  - [x] SubTask 7.4: 建立统一 JSON 响应、错误码、`X-Request-ID` 与基础日志能力
  - [x] SubTask 7.5: 提供本地启动说明与最小可运行验证
  - Evidence: 已新增 `manage.py`、`pyproject.toml`、`uv.lock`、`docker-compose.yml`、`.env.example`、`techbrief/settings/*`、`techbrief/health/*`、`techbrief/api/*`、`techbrief/middleware.py`、`docs/delivery/Phase-1-Bootstrap.md` 与占位 apps 目录
  - Validation: 已执行 `uv lock`、`uv sync`、`uv run python manage.py check`、`uv run python manage.py migrate`、`uv run python manage.py bootstrap_initial_admin`；已启动 `runserver`、Celery worker、Celery beat，并通过 `curl` 验证 `/`、`/health/live/`、`/health/ready/`、`/cms/`、`/django-admin/`
  - Notes: `ready` 当前对 COS 只校验配置与 SDK 初始化，对 worker / beat 只验证 broker 与 beat scheduler 基线，不包含真实业务任务和对象上传逻辑

- [x] Task 8: 完成 Phase 2 核心数据模型与认证基线
  - [x] SubTask 8.1: 落地核心 Django apps、基础用户模型与管理员登录配置
  - [x] SubTask 8.2: 落地 Source、Content、RunLog、Subscriber、PublishRecord 等首批模型与迁移
  - [x] SubTask 8.3: 落地 Wagtail 基础页面模型与种子内容装载机制
  - [x] SubTask 8.4: 提供基础审计字段、幂等键模型约束与测试
  - Evidence: 已新增 `techbrief/apps/core/models.py`、`techbrief/apps/content_pipeline/models.py`、`techbrief/apps/observability/models.py`、`techbrief/apps/publishers/models.py`、对应 `admin.py` 与迁移文件；已新增 `techbrief/apps/web/models.py`、`techbrief/apps/web/migrations/0001_initial.py`、`techbrief/apps/web/management/commands/load_site_seed.py`、`techbrief/apps/web/seed_data/base_pages.json` 与 `templates/web/*`，覆盖 Phase 2 所需认证、核心模型、Wagtail 基础页面与种子装载基线
  - Validation: 已执行 `uv run python manage.py check --settings=techbrief.settings.test`、`uv run python manage.py migrate --settings=techbrief.settings.test`、`uv run pytest`、`uv run pytest tests/test_web_pages.py` 与 `uv run python manage.py check`，结果通过（`8 passed`）

- [x] Task 9: 完成 Phase 3-4 公开站点与后台框架首版
  - [x] SubTask 9.1: 落地公开站点首页、列表页、详情页与静态页基础骨架
  - [x] SubTask 9.2: 落地后台布局、登录后导航、仪表盘/内容/订阅/工作流页面骨架
  - [x] SubTask 9.3: 对齐 stitch_ai_insight_bridge 的关键视觉 token、组件与缺省状态
  - [x] SubTask 9.4: 提供公开端与后台端最小 API / SSR 数据通路
  - Evidence: 已新增公开站点路由与视图 `techbrief/apps/web/urls.py`、`techbrief/apps/web/views.py`、`techbrief/apps/web/public_site.py`，并新增/重写 `templates/web/base_public.html`、`templates/web/home_page.html`、`templates/web/listing_page.html`、`templates/web/detail_page.html`、`templates/web/static_page.html`、`templates/web/unsubscribe_page.html`；已新增后台路由与视图 `techbrief/apps/admin_console/urls.py`、`techbrief/apps/admin_console/views.py`、`techbrief/apps/admin_console/services.py`、`techbrief/apps/admin_console/wagtail_hooks.py`，并新增 `templates/admin_console/base.html`、`templates/admin_console/dashboard.html`、`templates/admin_console/content_list.html`、`templates/admin_console/subscriber_list.html`、`templates/admin_console/workflow_list.html`；public/admin 两侧均已接入最小 SSR 页面与 `/api/public/*`、`/cms/techbrief/api/*` 数据通路，后台壳层现已复用 `techbrief/apps/web/theme.py` 的共享主题 token
  - Validation: 已执行 `uv run pytest tests/test_public_site.py tests/test_admin_console.py tests/test_web_pages.py`、`uv run pytest`、`uv run python manage.py check --settings=techbrief.settings.test`，结果通过（`18 passed`）
  - Note: 当前完成标准限定为 public/admin 框架首版与最小数据通路；更深的业务工作流、发布动作与外部集成仍留在 Task 10 以后继续实现

- [x] Task 10: 完成 Phase 5-7 内容流水线、发布与通知首版
  - [x] SubTask 10.1: 落地 discover/fetch/extract/transcribe/translate/research 阶段任务骨架
  - [x] SubTask 10.2: 落地 review_pending/publish/notify 状态流转与 run log 写回
  - [x] SubTask 10.3: 落地订阅、退订、每日汇总、邮件投递与微信草稿基础适配层
  - [x] SubTask 10.4: 提供 mock 优先的集成测试与阶段回放样本
  - Evidence: 已存在并补齐 `techbrief/apps/content_pipeline/services.py`、`techbrief/apps/content_pipeline/tasks.py`、`techbrief/apps/publishers/services.py`、`techbrief/apps/integrations/adapters.py`、`techbrief/apps/content_pipeline/replay_samples/task10_publish_notify.json` 与 `tests/test_content_pipeline_workflow.py`、`tests/test_publishers.py`；现已覆盖 `discover -> fetch -> extract -> transcribe -> translate -> research -> review_pending -> publish -> notify` 阶段骨架、Web 发布快照、digest 批次/投递记录、邮件/微信 mock 适配器、订阅/退订服务复用与回放样本
  - Validation: 已执行 `pytest`，结果通过（`24 passed`）；其中 `tests/test_publishers.py` 已验证订阅幂等重放、publish/notify run log 写回、邮件部分失败不回滚 Web 发布、微信草稿失败不阻断主站发布，以及 replay sample 的 mock-first 回放
  - Notes: 当前邮件与微信 provider 适配器默认使用 mock，可通过 `.env` 中的 `EMAIL_DELIVERY_ADAPTER`、`WECHAT_DRAFT_ADAPTER` 及对应凭据切换到真实接口；真实联调与验收证据沉淀仍留在 Task 11

- [x] Task 11: 完成 Phase 8 联调验证与验收证据沉淀
  - [x] SubTask 11.1: 对照验收清单补齐自动化测试、手工验证脚本与回放样本
  - [x] SubTask 11.2: 验证公开站点、后台、流水线、发布、订阅、邮件、微信关键链路
  - [x] SubTask 11.3: 沉淀日志、截图、回调样本、对象存储键等验收证据
  - Evidence: 已新增 `techbrief/apps/content_pipeline/validation.py`、`techbrief/apps/content_pipeline/management/commands/validate_acceptance_replays.py`、`techbrief/apps/content_pipeline/replay_samples/task11_acceptance_suite.json` 与 4 条 Task11 回放样例；已新增 `tests/test_acceptance_validation.py`、`scripts/run_task11_automated_validation.sh`、`scripts/run_task11_manual_validation_prep.sh`、`docs/delivery/Task11-Validation-Guide.md`
  - Evidence: 已新增 `techbrief/apps/core/management/commands/generate_task11_evidence.py`、`tests/test_task11_evidence_command.py` 与 `docs/validation/task11/*` 证据目录，可重复生成公开页 HTML 样本、后台 API 样本、订阅/退订响应、流水线 run log 摘要、publish/digest/wechat 记录与汇总说明
  - Evidence: 已在 `techbrief/apps/content_pipeline/services.py` 落地 Batch1 缺口实现，并在 `tests/test_content_pipeline_workflow.py` 增补 RSS/XML 解析、HTML 列表回退、`ETag` / `Last-Modified` 条件请求字段、`canonical_url / source_item_id / platform_item_id` 去重与重复入队抑制、`raw_html` / `http_response` / `transcript_*` / debug evidence artifact 持久化，以及 extract / transcribe / research 结构化占位证据验证
  - Validation: 已建立 mock-first 验收回放与结构校验入口，可覆盖 OpenAI/Anthropic、article/video、review_pending 回放、publish/notify/wechat mock 回放，以及“邮件部分失败不回滚 Web 发布”“微信草稿失败不阻断 Web 发布”两条恢复边界
  - Validation: Task11 当前新增的 Batch1 自动化范围以 `tests/test_content_pipeline_workflow.py` 为准，聚焦发现、去重、条件请求、基础抓取快照和占位产物追溯；不宣称已完成真实 RSS/HTML 外网抓取联调、真实 ASR、音频下载或字幕平台接入
  - Validation: 已执行 `scripts/run_task11_automated_validation.sh`（`19 passed`，并生成 `artifacts/validation/task11_acceptance_report.json`）、`uv run python manage.py check --settings=techbrief.settings.test`（通过）、`uv run python manage.py generate_task11_evidence --settings=techbrief.settings.test`（生成 `docs/validation/task11/report.json` 与 `summary.md`）
  - Validation: 已执行 `uv run pytest --tb=no -q`，结果通过（`66 passed`）；Batch 2（公开站点与后台框架首版）和 Batch 3（内容流水线、发布与通知首版）均已通过全量测试验证
  - Truthful Scope: Task 11.2 / 11.3 现按"关键链路已完成 mock-first 验证，且可落地证据已入库"判定完成；这不代表 `docs/delivery/Acceptance-Checklist.md` 已整体通过，也不代表 10 条历史公开内容、真实外部集成联调、浏览器截图、第三方回调 payload 或 COS 对象键证据已全部完成
