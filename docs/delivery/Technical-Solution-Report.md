# TechBrief MVP 技术方案调研报告

更新时间：2026-06-03

## 1. 报告目标

本报告基于 [TechBrief-PRD.md](file:///home/shixuan/code/TechBrief/TechBrief-PRD.md) 提取 MVP 核心需求，并对每个核心需求做技术调研、方案比选和推荐收敛。

目标不是直接开始编码，而是先回答三个问题：

1. 这些需求分别可以用什么技术实现；
2. 哪些方案更适合当前 MVP；
3. 最终应该组合成什么样的一套可落地架构。

## 2. 从 PRD 提取的核心需求

结合 PRD 的 P0、FR 和端到端流程，当前 MVP 可收敛为 8 个核心能力域：

| 核心需求 | 对应 PRD 关注点 |
|---|---|
| 公开 Web 站点 + 后台管理 | 公开首页/列表/详情、后台仪表盘/内容/订阅/工作流/渠道发布 |
| 内容发现与去重 | RSS 优先、列表页轮询、canonical/source_id 去重 |
| 文章抓取与结构化抽取 | 保存 raw HTML、抽正文、保留标题/列表/代码/链接 |
| 视频抓取、字幕与转录兜底 | 更多公开视频平台、优先字幕、无字幕则抽音频转录 |
| 中文翻译与研究报告 | 术语表、结构保真、无字幕视频生成研究报告 |
| 工作流调度、重试与可观测 | 2 小时巡检、失败阶段记录、从失败点重试 |
| 邮箱订阅与每日汇总 | 订阅/退订、每日 digest、投递结果追踪 |
| 微信公众号手动草稿发布 | 后台手动触发、复用封面/摘要/作者、记录 draft id |

## 3. 总体架构候选与推荐

### 3.1 候选路线

#### 方案 A：Django + Wagtail 单体应用 + Celery
- 适合内容站、后台、权限、表单、内容发布一体化交付。
- Wagtail `StreamField` 适合混合长文内容，能把标题、段落、图片、引用、视频等作为结构化 block 存储。
- Django admin 适合作为内部工具基座，但官方文档也明确更适合“组织内部的模型管理工具”，如果流程型页面较多，应补自定义 admin views。
- Celery + beat / `django-celery-beat` 适合定时任务、异步处理、失败重试。

#### 方案 B：FastAPI + React/Next.js + 独立任务系统
- API 分层清晰，前后端边界明确。
- 适合产品复杂、多人前端协作、未来多客户端扩展。
- 但对当前 MVP 来说，公开站点、后台、权限、内容编辑能力都要从零搭建，交付成本更高。

### 3.2 推荐结论

**推荐采用方案 A：Django + Wagtail + Celery + PostgreSQL/SQLite 分层演进。**

推荐原因：

1. 当前产品本质是“内容站 + 内部运营后台 + 异步内容流水线”，不是 API 平台优先；
2. Wagtail 天然适合博客/CMS 场景，可减少公开站点和编辑后台的重复建设；
3. Django 自带认证、权限、表单、管理后台，适合快速落地订阅管理、内容审核、手动发布页；
4. Celery 生态成熟，适合承接抓取、翻译、转录、邮件发送这类异步任务；
5. 对 MVP 来说，单体应用更符合“先交付可运行系统，再拆分”的策略。

### 3.3 推荐的模块边界

- `web`: 公开站点渲染、列表页、详情页、订阅入口
- `admin_console`: 自定义后台页面、仪表盘、工作流页、手动发布页
- `content_pipeline`: discover / fetch / extract / translate / transcribe / research
- `publishers`: web 发布、email digest、wechat draft
- `integrations`: OpenAI/Anthropic 来源、视频平台、翻译、邮件、微信
- `observability`: run log、阶段耗时、失败原因、重试入口

## 4. 分需求技术调研与推荐

### 4.1 公开 Web 站点 + 后台管理

#### 候选方案

- **Django + Wagtail**
  - 优点：站点路由、页面模型、内容 block、后台扩展、权限体系现成。
  - 风险：流程型后台页面不能只靠默认 admin，需要补自定义 views。
- **纯 Django + 自定义模板**
  - 优点：最简单可控。
  - 风险：内容编辑能力、页面管理能力弱，后续扩展成本高。
- **FastAPI + Next.js**
  - 优点：前后端边界清晰。
  - 风险：MVP 实现面更大。

#### 推荐方案

- 公开站点采用 **Wagtail Page + StreamField** 渲染；
- 后台分两层：
  - 模型型页面：用 Django/Wagtail admin 管理；
  - 流程型页面：用 Wagtail admin views 或 Django 自定义 staff-only views 实现仪表盘、工作流执行页、微信发布页。

#### 设计建议

- `ContentItem` 作为流水线源数据模型；
- 发布到站点时，将 `ContentItem` 的中文结构化内容同步为 `ArticlePage` / `VideoPage`；
- 站内页面是“发布快照”，流水线数据是“处理事实”，两者不要混为一个表。

### 4.2 内容发现与去重

#### 调研结论

- Trafilatura 当前文档和 README 显示支持 feed、sitemap、URL 发现，适合作为发现链路中的辅助工具。
- yt-dlp 支持大量视频站点，适合视频元信息、字幕、音频来源统一接入。
- PRD 要求 RSS 优先、无 RSS 时轮询列表页，因此发现层必须是“来源适配器”而不是单一爬虫。

#### 推荐方案

- 建立 `SourceAdapter` 抽象，分三类：
  - `RssSourceAdapter`
  - `HtmlListSourceAdapter`
  - `VideoChannelAdapter`
- 去重键固定为：
  - `dedupe_key = sha256(source + content_type + canonical_url_or_source_id)`
- 对发现结果保存：
  - `source_name`
  - `content_type`
  - `source_item_id`
  - `canonical_url`
  - `published_at`
  - `discovered_at`

#### 风险与对策

- **来源页面改版**：每个来源适配器单独维护，不共享脆弱 XPath。
- **同内容多 URL**：优先 canonical URL，其次最终跳转 URL，其次平台 ID。
- **重复入队**：发现入库时做唯一索引，任务入队前再做一次幂等校验。

### 4.3 文章抓取与结构化抽取

#### 候选方案

- **Trafilatura**
  - 优点：支持 metadata、Markdown/JSON/XML 输出、可保留链接/图片/格式。
  - 风险：需要注意版本许可边界。当前 README 标注 Apache 2.0，但旧版本曾为 GPLv3+，实施时必须锁定当前许可安全版本。
- **readability-lxml**
  - 优点：Apache 2.0，成熟简单，适合作为正文抽取 fallback。
  - 风险：结构化能力比 Trafilatura 弱。
- **Goose3**
  - 优点：Apache 2.0，可抽正文和元数据。
  - 风险：对复杂技术博客结构保真通常不如更偏结构化的方案。
- **jusText**
  - 优点：BSD，适合 boilerplate 去除。
  - 风险：更偏文本清洗，不是完整文章结构建模方案。

#### 推荐方案

- **主抽取器：Trafilatura**
- **回退抽取器：readability-lxml**
- **极端失败兜底：保留 raw HTML，允许人工修正**

#### 实现建议

- 抽取结果不要直接只存 Markdown，至少同时保留：
  - `raw_html`
  - `content_ast`
  - `content_md`
  - `metadata_json`
- `content_ast` 需要对齐 PRD 结构单元：`H1-H4`、`P`、`UL/OL`、`BLOCKQUOTE`、`CODE_BLOCK`、`IMAGE`、`HR`

### 4.4 视频抓取、字幕与转录兜底

#### 调研结论

- yt-dlp 官方项目支持 thousands of sites，且明确支持字幕、格式选择、后处理和 ffmpeg 集成。
- ffmpeg 官方文档支持从视频流中剥离音频，适合转录前标准化。
- faster-whisper 基于 CTranslate2，支持 CPU/GPU、INT8、batched transcription、VAD、词级时间戳，适合本地或自托管转录。

#### 推荐方案

- **视频元信息与字幕获取：yt-dlp**
- **音频提取与标准化：ffmpeg**
- **ASR 转录：faster-whisper**

#### 推荐处理链

1. 用 yt-dlp 获取视频 metadata 和可用字幕列表；
2. 若有人工字幕或自动字幕，优先拉取字幕；
3. 若无字幕，使用 yt-dlp/ffmpeg 获取音频；
4. 统一转为 `16kHz mono wav`；
5. 用 faster-whisper 转录，开启 `vad_filter`；
6. 输出：
   - `transcript_text`
   - `segments_json`
   - `language`
   - `transcription_confidence`（如可得）

#### 风险与对策

- **长视频成本高**：MVP 先限制时长或频道范围。
- **自动字幕质量波动**：记录 `text_source_status = subtitle | auto_subtitle | asr`。
- **平台限流**：视频平台适配器必须支持失败重试与退避。

### 4.5 中文翻译与研究报告

#### 调研结论

- PRD 对翻译的关键不是“能翻”，而是“结构保真 + 术语一致 + 可审核”。
- 因此不应直接整篇丢给 LLM，而应使用 **block-by-block** 处理。
- LangGraph 的持久化能力适合复杂 AI 图，但其价值主要体现在 checkpoint、replay、human-in-the-loop。

#### 推荐方案

- MVP 采用 **分块翻译器 + 术语表后处理 + 结构校验器**；
- 研究报告仅用于“无字幕视频转录稿”，不扩展到全部文章；
- LangGraph **不作为整站主编排器**，如后续需要复杂 AI 子流程重放，可只用于 `TranslateAndResearch` 子流水线。

#### 推荐处理策略

- 输入：`content_ast` / `transcript_text`
- 翻译：
  - 代码块、inline code、URL 直接保护；
  - 标题、段落、列表逐块翻译；
  - glossary 在 prompt 前置 + 输出后替换双保险；
- 校验：
  - 标题数量/层级
  - 代码块数量
  - 关键链接数量
- 研究报告：
  - 固定章节模板：背景 / 核心观点 / 技术点 / 产品影响 / 风险与限制 / 关键词

#### 为什么不推荐“全局 LangGraph 化”

- 当前系统的复杂度主要在“异步任务、来源适配、发布链路”，而不是多 agent 协作；
- 全局引入 LangGraph 会增加状态模型、持久化和运维复杂度；
- 先用普通任务编排落地 MVP，更符合当前阶段。

### 4.6 工作流调度、重试与可观测

#### 候选方案

- **APScheduler**
  - 优点：轻量、可嵌入应用。
  - 风险：更适合单进程调度；多实例场景要自己处理抢占、重复执行、持久化一致性。
- **Celery + celery beat**
  - 优点：异步任务、重试、worker 扩展成熟。
  - 风险：需要 broker。
- **Celery + django-celery-beat**
  - 优点：周期任务可存数据库，并可在 Django Admin 中管理。
  - 风险：需要处理 timezone 变更和单 scheduler 约束。

#### 推荐方案

- **异步执行：Celery**
- **周期调度：django-celery-beat**
- **状态追踪：应用数据库中的 `RunLog` + `ContentItem` 状态字段**

#### 推荐执行模型

- 定时 discover：每 2 小时触发
- 每条内容以 stage 驱动：
  - `discover`
  - `fetch`
  - `extract`
  - `transcribe`
  - `translate`
  - `research`
  - `review_pending`
  - `publish`
  - `notify`
- 每个 stage 结束都落一条 `RunLog`
- 失败后记录：
  - `last_error_stage`
  - `last_error_code`
  - `last_error_message`

#### 重试建议

- 网络类错误：自动指数退避
- 结构类错误：转人工
- 邮件/微信错误：独立重试，不回滚已发布状态

### 4.7 邮箱订阅与每日汇总

#### 候选方案

- **Resend**
  - 优点：接入简单、域名验证快、测试地址友好、Webhook 机制清晰。
  - 风险：更偏开发者体验，复杂营销能力不是重点。
- **Postmark**
  - 优点：事务邮件口碑强、webhook 丰富、Message Streams 清晰。
  - 风险：本身不提供订阅列表管理，需要业务侧自己维护。

#### 推荐方案

- MVP 优先 **Resend**
- 通过 `EmailProviderAdapter` 隔离供应商，保留后续切换 Postmark 的空间

#### 推荐链路

1. 站内提交邮箱 -> `Subscriber(active)`；
2. 发送确认或直接进入 active（由产品决定）；
3. 每日固定时间查询当天 `published` 内容；
4. 生成 digest 模板；
5. 调用 provider 发送；
6. 保存 `PublishRecord(channel=email)`；
7. 通过 webhook 或 provider API 回写投递状态。

#### 关键约束

- 每封邮件必须携带退订入口；
- 每个订阅者必须有状态字段：`active / unsubscribed / bounced`；
- 邮件发送必须和站内发布解耦，发送失败不影响内容已发布状态。

### 4.8 微信公众号手动草稿发布

#### 调研结论

- 微信官方 `draft_add` 文档明确要求 **只能服务端调用**，不能前端直连。
- 草稿发布后会从草稿箱移除，因此公众号草稿箱不能当主存储。
- `news` 类型要求 `thumb_media_id` 为永久素材；
- `content` 支持 HTML，但图片 URL 必须来自微信图文内图片上传链路，外链图片会被过滤。

#### 推荐方案

- 将微信能力定义为 **后台独立手动工具**，不进入自动主流程；
- 发布链路拆为：
  - 站内内容 -> HTML 渲染
  - 封面上传为永久素材
  - 正文图片上传为微信图文图片
  - 调用 `draft_add`
  - 保存 `wechat_draft_id`

#### 为什么不推荐“直接复用站内 HTML”

- 微信 HTML 不是通用浏览器 HTML；
- 外链图片会被过滤；
- 样式支持受限；
- 因此需要单独的 `wechat_html_renderer`。

#### 推荐后台交互

- 来源 1：选择站内已发布内容，自动填充标题/作者/摘要/封面/正文
- 来源 2：纯手工录入
- 点击创建草稿后显示：
  - `wechat_draft_id`
  - 请求摘要
  - 错误码
  - 重试入口

## 5. 推荐的 MVP 技术组合

### 5.1 应用层

- Python 3.14
- uv
- Django
- Wagtail
- Jinja/Django Templates（站点 SSR）

### 5.2 数据与任务

- SQLite：本地 MVP 数据库
- PostgreSQL：进入多人/生产后升级
- Redis：Celery broker / cache / 限流辅助
- Celery
- django-celery-beat

### 5.3 内容处理

- HTTP 抓取：`httpx`
- 正文抽取：Trafilatura 主用，readability-lxml fallback
- 视频抓取：yt-dlp
- 音频处理：ffmpeg
- 转录：faster-whisper

### 5.4 AI 与分发

- 翻译：可配置 LLM provider（保留 Minimax/其他供应商适配层）
- 邮件：Resend
- 微信：Official Account Draft API

## 6. 需要提前确认的实施前置条件

### 6.1 外部依赖

- Redis 是否允许引入
- 邮件域名与 DNS 配置谁来提供
- 微信公众号账号类型、权限、AppID/AppSecret 是否具备
- 视频来源范围是否只做官方频道，是否需要白名单

### 6.2 业务边界

- 对视频时长是否设置上限
- 无字幕视频是否全部转录，还是按优先级转录
- 研究报告是否站内公开，还是仅后台可见
- 邮件订阅是否采用 double opt-in

## 7. 主要风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| 来源站点改版 | 抓取失败 | 来源适配器隔离、raw HTML 留存、人工修正规则 |
| 视频平台限流/变更 | 视频处理失败 | yt-dlp 统一封装、失败重试、平台白名单 |
| 转录成本与耗时偏高 | 队列堆积 | 时长限制、优先级队列、GPU/CPU 分层 |
| 翻译结构漂移 | 页面质量下降 | block 翻译、结构校验、人工审核 |
| 邮件投递波动 | 订阅体验下降 | provider webhook、失败重发、bounce 状态管理 |
| 微信素材与 HTML 约束 | 草稿创建失败 | 独立 renderer、图片先上传微信、仅后台手动使用 |

## 8. 最终推荐结论

如果目标是尽快交付一个可运行、可运营、可追溯的 TechBrief MVP，推荐采用：

- **Django + Wagtail** 负责公开站点与后台；
- **Celery + django-celery-beat + Redis** 负责异步处理与调度；
- **Trafilatura/readability-lxml** 负责文章抽取；
- **yt-dlp + ffmpeg + faster-whisper** 负责视频、字幕、音频与转录；
- **LLM 分块翻译 + 术语表 + 结构校验** 负责中文内容生产；
- **Resend** 负责邮件订阅与每日汇总；
- **微信草稿 API** 作为后台独立手动发布工具。

这套组合满足当前 PRD 的所有 P0 核心能力，同时保留后续升级路径：

- SQLite -> PostgreSQL
- 单体站点 -> 多实例部署
- 规则型任务编排 -> 局部引入 LangGraph 做 AI 子流程重放
- 单 provider -> 多 provider adapter

## 9. 调研依据（官方/项目资料）

- Wagtail StreamField: https://docs.wagtail.org/en/stable/topics/streamfield.html
- Django Admin: https://django.readthedocs.io/en/5.2.x/ref/contrib/admin/
- LangGraph Persistence: https://docs.langchain.com/oss/javascript/langgraph/persistence
- Trafilatura: https://github.com/adbar/trafilatura
- readability-lxml: https://pypi.org/project/readability-lxml/
- Goose3: https://github.com/goose3/goose3
- jusText: https://pypi.org/project/jusText/
- yt-dlp: https://github.com/yt-dlp/yt-dlp
- faster-whisper: https://github.com/SYSTRAN/faster-whisper
- APScheduler: https://apscheduler.readthedocs.io/en/stable/userguide.html
- Celery Periodic Tasks: https://github.com/celery/celery/blob/main/docs/userguide/periodic-tasks.rst
- django-celery-beat: https://github.com/celery/django-celery-beat
- Resend: https://resend.com/docs/hackathon
- Postmark: https://postmarkapp.com/developer/api/webhooks-api
- WeChat Draft Add API: https://developers.weixin.qq.com/doc/service/api/draftbox/draftmanage/api_draft_add.html
- FFmpeg: https://ffmpeg.org/ffmpeg.html
