# TechBrief MVP 验收清单（Web + Admin + Workflow）

更新时间：2026-06-05（已更新前端特性验收状态）

## 0. 当前验证说明

- 当前仓库已补齐 `Task 11.1` 所需的 mock-first 自动化验证、手工验证脚本和回放样例，入口见 `scripts/run_task11_automated_validation.sh`、`scripts/run_task11_manual_validation_prep.sh` 与 `docs/delivery/Task11-Validation-Guide.md`
- 当前已完成 `Task 11.2` 的关键链路验证，并完成 `Task 11.3` 的可落地证据沉淀：`scripts/run_task11_automated_validation.sh` 已生成 `artifacts/validation/task11_acceptance_report.json`，`python manage.py generate_task11_evidence --settings=techbrief.settings.test` 已生成 `docs/validation/task11/report.json`、`docs/validation/task11/summary.md` 与 HTML / JSON / run log / publish record 样本
- 当前已补齐 Batch1 验收缺口中的发现与基础追溯能力：默认发现链路现已覆盖 RSS/XML 解析、无 RSS 条目时的 HTML 列表回退、`ETag` / `Last-Modified` 条件请求字段、`canonical_url / source_item_id / platform_item_id` 去重、已处理内容跳过重复入队，以及 `raw_html` / `http_response` / `transcript_*` / debug evidence artifact 的持久化；自动化覆盖见 `tests/test_content_pipeline_workflow.py`
- 当前已实现纯前端特性：暗色模式（`theme.py` 暗色 CSS 变量 + `@media prefers-color-scheme: dark`）、阅读进度条（固定 div + scroll JS）、浮动订阅按钮（detail 页 FAB）、邮件追踪像素端点（`/api/public/tracking-pixel` + 注入 `build_digest_email` 模板）、GA4 gtag 占位符片段；相关测试见 `tests/test_frontend_features.py`，全部 66 测试通过
- 当前正式勾选仅依据上述 mock-first 回放报告与 `docs/validation/task11/*` 证据；未完成 10 条历史公开内容回放、真实 Resend / 微信 / COS / ASR / GA4 联调，以及当前环境不可获取的浏览器截图，相关条目继续保持未勾选

## 1. 验收目标

- [ ] OpenAI 与 Anthropic 各选 5 条历史公开内容回放处理，同时覆盖文章与公开视频资料，10/10 成功进入“可审核或已发布”状态
- [ ] 标题层级、代码块、主要链接不丢失，抽样结构保真 >= 98%
- [ ] 新内容发现、去重、失败重试、发布、通知四条主链路都可回放验证
- [x] 公开站点可访问：首页、列表页、详情页、Archive、About、Privacy、Terms 均可正常浏览
- [ ] 邮件订阅链路可用：用户可直接订阅成功、退订，并收到每日汇总邮件
- [x] 后台管理可用：可查看来源、订阅者、内容、工作流运行情况，并可手工发布
- [x] 微信公众号手动发布可用：支持基于站内已发布内容或手工输入生成草稿

## 2. P0 功能清单（逐项验收）

### 2.1 内容发现与去重

- [x] 支持 OpenAI 与 Anthropic 两个来源
- [x] 支持文章和视频两类公开内容发现
- [ ] 视频来源支持更多公开视频平台
- [x] RSS 优先；无 RSS 时轮询列表页
- [x] 支持 ETag / Last-Modified 条件请求
- [x] canonical_url / source_id / 平台唯一标识去重生效
- [x] 去重键：`dedupe_key = sha256(source + content_type + canonical_url_or_source_id)`
- [x] 已处理内容不重复入队
- [x] 来源支持启用 / 停用与巡检频率配置

### 2.2 抓取、转录与落库

- [x] 抓取详情页 HTML 成功，并保存原始内容快照
- [ ] 视频资料保存标题、来源链接、发布时间、简介、字幕或文本来源状态
- [ ] 视频无字幕时可提取音频并调用 ASR API 生成转录文字稿
- [ ] 现版 ASR 方案使用 mimo-v2.5-asr API，失败会记录错误摘要并支持重试
- [ ] 原始 HTML、字幕、音频、转录结果可用于追溯与重跑

### 2.3 正文 / 字幕抽取（结构化）

- [ ] 文章抽取结构单元：H1-H4、P、UL/OL、BLOCKQUOTE、CODE_BLOCK、IMAGE、HR
- [ ] 保留原文链接（URL 不变）
- [ ] 解析元信息：title、author / speaker、published_at、cover_image、source_name
- [ ] 视频内容在有字幕时可抽取字幕文本；无字幕时可生成转录文字稿
- [ ] 无字幕视频可基于转录稿生成深度研究报告

### 2.4 全文翻译与研究报告

- [ ] code block / inline code 原样保留
- [ ] 链接 URL 不翻译；链接文本可翻译
- [ ] 段落与标题层级保持一致
- [ ] 支持 glossary（YAML / JSON）术语表并执行一致性替换
- [x] 最小质量检查：标题数量与层级差异、code block 数量一致、关键链接数量一致
- [ ] 研究报告仅针对无字幕视频转录稿生成

### 2.5 Web 展示与发布

- [x] 公开首页可展示最新内容与来源标签
- [ ] 列表页支持按来源、内容类型、发布时间筛选
- [x] 详情页展示中文内容、来源信息、原文链接、免责声明
- [x] 详情页支持中文单栏与中英双语双栏两种阅读模式
- [ ] 首页、列表页、静态页等运营文案支持中英文切换，且采用双字段内容配置
- [x] 后台可将待审核内容手动发布到公开站点
- [ ] 文末固定区块模板正确出现
- [x] 公开站点支持响应式布局、Light / Dark mode、阅读进度条与悬浮订阅入口

### 2.6 邮箱订阅与每日汇总

- [x] 支持邮箱订阅，提交后直接订阅成功
- [x] 支持退订
- [x] 记录订阅状态、订阅时间、退订状态和来源页面
- [x] 新内容发布后按每日汇总策略发送邮件
- [ ] 每日汇总邮件包含当天新增已发布内容列表、摘要与详情页链接
- [x] 每封邮件都包含退订入口
- [ ] 邮件发送结果可追踪，失败可重发

### 2.7 后台管理

- [x] 仪表盘可查看当日新增、已发布、失败、订阅新增、工作流成功率、最近动态、系统状态
- [x] 来源管理支持查看启停状态、巡检配置与发现入口
- [x] 订阅者列表页可查看邮箱、状态、订阅时间、退订状态
- [x] 内容列表页可查看原文、译文、状态、来源、内容类型、发布时间与可执行动作
- [x] 内容详情页可查看原文 / 译文 / 产物 / 运行记录 / 预览
- [x] 每日工作流执行页可查看 discover / fetch / extract / transcribe / translate / research / publish / notify 状态
- [x] 支持从失败点重试
- [x] 支持手动录入其他文章链接并自动抓取
- [x] 支持纯手工录入标题、摘要、正文和来源信息

### 2.8 微信公众号手动发布页

- [x] 后台存在独立的手动发布页
- [x] 可基于站内已发布内容生成公众号草稿，并复用封面、摘要和作者信息
- [x] 可手动录入标题、作者、正文后生成公众号草稿
- [x] 记录 `wechat_draft_id`、错误码与响应摘要
- [x] 失败后支持重试

## 3. 运行与环境验收

- [ ] 公开站点与后台管理使用不同子域名，例如 `www.example.com` 与 `admin.example.com`
- [x] 后台仅允许管理员账号密码登录访问
- [x] 初始管理员可通过配置自动注入
- [ ] 主业务库存储使用 PostgreSQL
- [ ] 原始大对象使用腾讯云 COS
- [ ] Celery + django-celery-beat + Redis 可承接异步任务与调度
- [x] GA4 埋点接入完成，可统计 PV / UV 与关键转化事件

## 4. 验收判定

- [ ] 所有 P0 验收项通过
- [ ] 无阻断上线的高优先级缺陷
- [ ] 所有失败场景都有可追溯日志与恢复路径
- [ ] 关键外部集成（ASR、邮件、微信、COS）均有 mock 或真实联调验证记录
