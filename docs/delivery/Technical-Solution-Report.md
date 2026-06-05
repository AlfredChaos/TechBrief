# TechBrief MVP 技术方案调研报告

更新时间：2026-06-03

## 1. 报告目标

本报告基于 [TechBrief-PRD.md](file:///home/shixuan/code/TechBrief/TechBrief-PRD.md) 提取 MVP 核心需求，并收敛为一套可执行的技术方案、模块边界和实现约束。

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
| 工作流调度、重试与可观测 | 定时巡检、失败阶段记录、从失败点重试 |
| 邮箱订阅与每日汇总 | 订阅/退订、每日 digest、投递结果追踪 |
| 微信公众号手动草稿发布 | 后台手动触发、复用封面/摘要/作者、记录 draft id |

## 3. 总体架构与模块边界

### 3.1 总体方案

**推荐采用方案 A：Django + Wagtail + Celery + 自有 PostgreSQL + 腾讯云 COS。**

这套组合适合当前 MVP，原因是：

1. 当前产品本质是“内容站 + 内部运营后台 + 异步内容流水线”，不是 API 平台优先；
2. Wagtail 天然适合博客/CMS 场景，可减少公开站点和编辑后台的重复建设；
3. Django 自带认证、权限、表单、管理后台，适合快速落地订阅管理、内容审核、手动发布页；
4. Celery 生态成熟，适合承接抓取、翻译、转录、邮件发送这类异步任务；
5. 自有 PostgreSQL + 腾讯云 COS 便于把“业务核心数据”和“原始大对象”分层存放。

### 3.2 核心模块

- `web`: 公开站点渲染、列表页、详情页、订阅入口
- `admin_console`: 自定义后台页面、仪表盘、工作流页、手动发布页
- `content_pipeline`: discover / fetch / extract / translate / transcribe / research
- `publishers`: web 发布、email digest、wechat draft
- `integrations`: OpenAI/Anthropic 来源、视频平台、翻译、邮件、微信
- `observability`: run log、阶段耗时、失败原因、重试入口

### 3.3 核心数据流

1. `discover`：从官方列表页 / RSS / sitemap 发现新增内容；
2. `fetch`：抓取详情页 HTML、视频元信息、字幕或音频来源；
3. `extract`：生成 `content_ast`、`content_md`、`metadata_json`；
4. `translate/research`：生成 `zh_ast`、`zh_md`、`research_report_md`；
5. `review/publish`：进入后台审核并发布到 Web；
6. `notify`：对已发布内容发送每日汇总邮件，按需手动生成微信草稿。

## 4. 分需求方案设计

### 4.1 公开 Web 站点 + 后台管理

#### 最终方案

- 公开站点采用 **Wagtail Page + StreamField** 渲染；
- 后台分两层：
  - 模型型页面：用 Django/Wagtail admin 管理；
  - 流程型页面：用 Wagtail admin views 或 Django 自定义 staff-only views 实现仪表盘、工作流执行页、微信发布页。
- 域名拆分采用：
  - `www.example.com`（示例）承载公开站点；
  - `admin.example.com`（示例）承载后台管理。
- 公开站点页面范围包含：首页、列表页、详情页、Archive、About、Privacy、Terms，并在导航中预留外部 API / Feed 入口。

#### 设计要点

- `ContentItem` 作为流水线源数据模型；
- 发布到站点时，将 `ContentItem` 的中文结构化内容同步为 `ArticlePage` / `VideoPage`；
- 站内页面是“发布快照”，流水线数据是“处理事实”，两者不要混为一个表。
- 公开站点接入 **Google Analytics 4**，用于统计 UV、PV、内容详情页访问量和订阅入口转化。
- 后台仅采用 Django 默认认证体系 + 管理员账号密码登录，不引入复杂角色权限模型。
- 项目启动时从配置文件读取初始管理员账号密码；若数据库中不存在对应管理员，则自动创建并写入数据库。
- 详情页默认支持中文阅读，并提供中英双语双栏模式切换。
- 首页、列表页、Archive、About、Privacy、Terms 等公开站点运营文案采用中英双字段存储，由 SSR 根据站点语言偏好选择对应字段渲染。
- 公开站点需实现响应式布局、Light / Dark mode、阅读进度条与悬浮订阅入口。
- 订阅交互采用弹窗或等价浮层，并提供提交成功后的成功态反馈。
- 后台仪表盘除核心指标外，还需要最近动态与系统状态摘要。
- 后台内容与订阅列表页需支持搜索、筛选、排序和预览；工作流页需提供时间线 / 日志视图。

### 4.2 内容发现与去重

#### 最终方案

- 建立 `SourceAdapter` 抽象，分三类：
  - `RssSourceAdapter`
  - `HtmlListSourceAdapter`
  - `VideoChannelAdapter`
- 对首批来源落成明确规则：
  - **Anthropic**：`news` + `research` 作为主发现源，`sitemap.xml` 作为补漏与 `lastmod` 校验；
  - **OpenAI**：`news/rss.xml` 作为主发现源，`research/index/` 作为研究类补充入口，栏目子 sitemap 作为补漏；
  - **OpenAI 多语言路径**：以非 locale 的 canonical URL 为主键，避免 `zh-Hans-CN` 等本地化路径重复入库。
- 去重键固定为：
  - `dedupe_key = sha256(source + content_type + canonical_url_or_source_id)`
- 对发现结果保存：
  - `source_name`
  - `content_type`
  - `source_item_id`
  - `canonical_url`
  - `published_at`
  - `discovered_at`

#### 设计要点

- 首批官方来源采用“官方发现源优先”策略，避免把搜索结果当作主监控真相源；
- Tavily / Exa 不进入主监控链路，只作为后续补充搜索能力的可选扩展。

#### 风险与对策

- **来源页面改版**：每个来源适配器单独维护，不共享脆弱 XPath。
- **同内容多 URL**：优先 canonical URL，其次最终跳转 URL，其次平台 ID。
- **重复入队**：发现入库时做唯一索引，任务入队前再做一次幂等校验。

### 4.3 文章抓取与结构化抽取

#### 最终方案

- **主抓取方式：直接请求官方详情页 URL**
- **主抽取器：Trafilatura**
- **回退抽取器：readability-lxml**
- **远程预处理 fallback：Jina Reader（仅在正文抽取失败或 HTML 噪音过高时启用）**
- **极端失败兜底：保留 raw HTML，允许人工修正**

#### 设计要点

- 主链路固定为：**官方列表页 / RSS / sitemap -> `httpx` 直连 -> Trafilatura 抽取**；
- `readability-lxml` 和 `Jina Reader` 仅作正文抽取 fallback，不承担主发现职责；
- Trafilatura 需要锁定明确可接受的版本，避免误用历史 GPL 阶段版本。
- 抽取后的结构化内容需要同时支持“中文单栏渲染”和“中英双栏对照渲染”两种展示模式。

#### 实现建议

- 抽取结果不要直接只存 Markdown，至少同时保留：
  - `raw_html`
  - `content_ast`
  - `content_md`
  - `metadata_json`
- `content_ast` 需要对齐 PRD 结构单元：`H1-H4`、`P`、`UL/OL`、`BLOCKQUOTE`、`CODE_BLOCK`、`IMAGE`、`HR`
- 存储落点建议明确分层：
  - **对象存储**：`raw_html`、原始响应快照、字幕原文、转录分段 JSON、音频文件、封面与原始图片等“大对象 / 原始证据”；
  - **关系型数据库**：`content_ast`、`content_md`、`metadata_json`、去重键、状态、错误、发布时间、发布记录等“业务核心数据”；
  - **数据库仅保存对象存储引用**：如 `storage_key`、`sha256`、`size`、`content_type`、`fetched_at`，避免把大文件直接塞进主业务表。

### 4.4 视频抓取、字幕与转录兜底

#### 最终方案

- **视频元信息与字幕获取：yt-dlp**
- **音频提取与标准化：ffmpeg**
- **ASR 转录：mimo-v2.5-asr API（当前版本）**
- **后续迭代预留：faster-whisper 自托管兜底**

#### 处理链

1. 用 yt-dlp 获取视频 metadata 和可用字幕列表；
2. 若有人工字幕或自动字幕，优先拉取字幕；
3. 若无字幕，使用 yt-dlp/ffmpeg 获取音频；
4. 统一转为 `16kHz mono wav` 或兼容 `audio/wav` 的标准音频；
5. 调用 mimo `https://api.xiaomimimo.com/v1/chat/completions`，使用 `model=mimo-v2.5-asr`，通过 `api-key` 或 `Authorization: Bearer` 认证发送 base64 data URL 音频；
6. `asr_options.language` 当前支持 `auto | zh | en`，MVP 默认建议对官方英文频道显式传 `en`，降低误判；
7. 优先输出：
   - `transcript_text`
   - `language`（若接口显式返回或由调用参数确定）
   - `provider_response_meta`（如 `usage.seconds`、token 使用量、request_id）
8. `segments_json`、`transcription_confidence` 属于可选扩展字段；当前 mimo 文档未保证返回，MVP 允许为空，后续如切换或补充 provider 再填充；

#### 风险与对策

- **长视频成本高**：MVP 先限制时长或频道范围。
- **自动字幕质量波动**：记录 `text_source_status = subtitle | auto_subtitle | asr`。
- **平台限流**：视频平台适配器必须支持失败重试与退避。
- **外部 ASR API 成本/限流**：增加请求超时、重试退避、音频时长上限与预算告警；后续需要时再评估引入自托管 ASR。

### 4.5 中文翻译与研究报告

#### 最终方案

- MVP 采用 **分块翻译器 + 术语表后处理 + 结构校验器**；
- 研究报告仅用于“无字幕视频转录稿”，不扩展到全部文章；
- LangGraph **不作为整站主编排器**，如后续需要复杂 AI 子流程重放，可只用于 `TranslateAndResearch` 子流水线。

#### 处理策略

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

#### 最终方案

- **异步执行：Celery**
- **周期调度：django-celery-beat**
- **状态追踪：应用数据库中的 `RunLog` + `ContentItem` 状态字段**

#### 执行模型

- 定时 discover：调度能力保留更高频扩展，但针对首批 **Anthropic / OpenAI 官方文章源建议每日 1 次**
- 每日巡检优先扫描：
  - Anthropic：`news`、`research`、`sitemap.xml`
  - OpenAI：`news/rss.xml`、`research/index/`、相关子 sitemap
- 增量判定规则：
  - canonical URL 不存在 -> 新增入队
  - 已存在但 `lastmod` / 列表页日期变化 -> 更新入队
  - 已存在且未变化 -> 跳过
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

#### 最终方案

- MVP 优先 **Resend**
- 通过 `EmailProviderAdapter` 隔离供应商，保留后续切换 Postmark 的空间

#### 处理链路

1. 站内提交邮箱 -> `Subscriber(active)`；
2. 每日固定时间查询当天 `published` 内容；
3. 生成 digest 模板；
4. 调用 provider 发送；
5. 保存 `PublishRecord(channel=email)`；
6. 通过 webhook 或 provider API 回写投递状态。

#### 关键约束

- 每封邮件必须携带退订入口；
- 每个订阅者必须有状态字段：`active / unsubscribed / bounced`；
- 邮件发送必须和站内发布解耦，发送失败不影响内容已发布状态。
- 公开站点应在导航、首页 Hero、文章详情页悬浮按钮等位置提供订阅入口；
- 订阅浮层需要区分“填写态 / 提交中 / 成功态”三种前端状态。

### 4.8 微信公众号手动草稿发布

#### 最终方案

- 将微信能力定义为 **后台独立手动工具**，不进入自动主流程；
- 发布链路拆为：
  - 站内内容 -> HTML 渲染
  - 封面上传为永久素材
  - 正文图片上传为微信图文图片
  - 调用 `draft_add`
  - 保存 `wechat_draft_id`

#### 设计要点

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
- Tailwind CSS（或等价 utility-first 样式体系）
- 少量前端交互层：原生 JS / Alpine.js / HTMX 三选一即可，优先最轻方案

#### 域名与后台认证

- 主站与后台采用不同子域名，例如 `www.example.com` 和 `admin.example.com`；
- 公开站点直接访问，后台仅允许管理员登录后访问；
- MVP 仅支持单管理员或少量管理员账号，不设计复杂 RBAC；
- 初始管理员通过配置文件提供，应用启动时执行幂等注入。

#### 前端体验约束

- 公开站点按原型实现响应式布局，至少覆盖 Desktop / Tablet / Mobile；
- 公开站点支持 Light / Dark mode；
- 详情页实现阅读进度条、中英阅读模式切换、悬浮订阅 CTA；
- 订阅交互以弹窗或等价浮层实现，避免跳转到独立表单页。

### 5.2 数据与任务

- PostgreSQL：使用现有自部署实例，保存业务核心数据
- 腾讯云 COS：保存 raw HTML、字幕、音频、原图等原始与大体积产物
- Redis：Celery broker / cache / 限流辅助
- Celery
- django-celery-beat

#### 数据库迁移策略

- PostgreSQL 的 schema migration 统一使用 **Django migrations**；
- Django / Wagtail / 业务模型都共享同一套迁移体系，避免出现双迁移源；
- 数据迁移优先使用 Django migration 中的 `RunPython`；
- 复杂 SQL 变更优先使用 Django migration 中的 `RunSQL`；
- **不引入 Alembic**，避免和 Django ORM / Wagtail 的迁移机制重复建设并产生漂移。

#### 存储分层策略

- **关系型数据库是 source of truth**
  - 保存 `ContentItem`、`RunLog`、`PublishRecord`、`Subscriber` 及其状态流转；
  - 保存审核、发布、去重、查询、筛选所需字段；
  - 保存可直接支撑站内渲染和后台管理的结构化数据。
- **对象存储是 artifact store**
  - 保存 `raw_html`、原始抓取响应、字幕文件、转录中间产物、音频、封面原图、调试导出文件；
  - 这些内容以文件形式存放，不参与复杂联查。
- **翻译后的文章与结构化正文放关系型数据库**
  - 推荐落库：`content_ast`、`content_md`、`zh_ast`、`zh_md`、`research_report_md`；
  - 原因是它们需要参与审核、版本管理、结构校验、站内发布和多渠道分发。
- **原始大对象放对象存储，不直接塞进主业务表**
  - 推荐落库字段：`raw_html_storage_key`、`sha256`、`size`、`content_type`、`fetched_at`；
  - 数据库只保留索引和引用，避免主表膨胀、查询变慢和备份成本升高。
- **MVP 允许临时降级**
  - 若早期未接入对象存储，可短期把 `raw_html` 放在 PostgreSQL 的文本字段中；
  - 但进入稳定运行阶段后，建议迁移到对象存储，数据库仅保留引用。

#### 腾讯云 COS Bucket 目录结构建议

- 推荐单 Bucket，多环境通过前缀隔离，而不是每类文件单独建 Bucket。
- 推荐对象 key 前缀：
  - `techbrief/{env}/content-items/{content_id}/...`
- 其中：
  - `env` 取值如 `local` / `staging` / `prod`
  - `content_id` 使用数据库中的 `ContentItem.id`，推荐采用 UUID，避免后续迁移或合并环境时冲突

- 推荐目录结构：

```text
techbrief/
  prod/
    content-items/
      {content_id}/
        manifest.json
        raw/
          html/source.html
          http/response.json
        metadata/
          source.json
        subtitles/
          manual/{lang}.vtt
          auto/{lang}.vtt
        transcripts/
          asr/transcript.txt
          asr/segments.json
        audio/
          source.wav
        media/
          cover/original.{ext}
          images/{image_hash}.{ext}
        debug/
          extraction-preview.md
          translation-preview.md
```

- 各目录职责：
  - `manifest.json`：该 `content_id` 在对象存储中的所有对象清单，用于快速排查和迁移；
  - `raw/`：原始网页源码与原始 HTTP 响应快照；
  - `metadata/`：来源页原始元信息、发现快照；
  - `subtitles/`：人工字幕或自动字幕；
  - `transcripts/`：ASR 转录文本与分段 JSON；
  - `audio/`：转录前保存的标准化音频；
  - `media/`：封面图与正文原始图片；
  - `debug/`：仅用于调试和验收的中间导出文件。

#### 通过文章 ID 快速定位对象的策略

- 可以，通过 `content_id` 前缀直接定位该文章的所有对象：
  - `techbrief/{env}/content-items/{content_id}/`
- 推荐采用“双索引”方案：
  - **对象存储前缀索引**：所有与同一文章关联的对象统一挂在同一 `content_id` 前缀下；
  - **数据库引用索引**：在 PostgreSQL 中保存对象引用，推荐单独建 `ContentArtifact` 表。

- `ContentArtifact` 建议字段：
  - `id`
  - `content_item_id`
  - `artifact_type`（如 `raw_html` / `subtitle_manual` / `subtitle_auto` / `audio` / `transcript_segments` / `cover_image`）
  - `storage_key`
  - `content_type`
  - `size`
  - `sha256`
  - `created_at`

- 查询策略：
  - 应用层日常访问：优先查 PostgreSQL 中的 `ContentArtifact`；
  - 排障 / 运维：直接按 COS prefix 列举 `techbrief/{env}/content-items/{content_id}/`；
  - 数据迁移 / 对账：以 `manifest.json` + `ContentArtifact` 双向校验。

- 推荐结论：
  - **对象 key 以 `content_id` 为主前缀**，不要以日期或来源作为第一层索引；
  - 日期、来源、类型更适合作为数据库字段查询条件，而不是对象存储的主定位键；
  - 这样可以确保“给定文章 ID，快速定位全部关联对象”这一需求天然成立。

### 5.3 内容处理

- HTTP 抓取：`httpx`（主链路）
- 正文抽取：Trafilatura 主用，readability-lxml fallback
- 远程预处理：Jina Reader（仅 fallback，不进入主监控链路）
- 视频抓取：yt-dlp
- 音频处理：ffmpeg
- 转录：mimo-v2.5-asr API（MVP），faster-whisper 仅作为后续自托管预研选项

### 5.4 AI 与分发

- 翻译：可配置 LLM provider（保留 Minimax/其他供应商适配层）
- 邮件：Resend
- 微信：Official Account Draft API

### 5.5 站点分析

- Google Analytics 4：统计公开站点 PV、UV、内容详情页访问量与关键转化事件

#### 推荐事件设计

- `page_view`：基础页面浏览事件，用于首页、列表页、详情页的 PV/UV 统计；
- `view_content_detail`：内容详情页浏览事件，附带 `content_id`、`content_type`、`source_name`、`slug`；
- `filter_content_list`：列表页筛选事件，附带 `source`、`content_type`、`date_range`；
- `click_subscribe_entry`：订阅入口点击事件，附带 `page_type`、`content_id`（如有）；
- `subscribe_success`：订阅成功事件，附带 `source_page`，用于计算订阅转化率。

#### 接入建议

- 在公开站点模板层统一注入 GA4 基础脚本；
- 页面浏览优先复用 GA4 默认 `page_view`，业务行为使用自定义事件补充；
- 事件参数命名保持稳定，避免后续报表口径漂移；
- 仅在公开站点接入，不把后台管理页面纳入默认统计范围。

### 5.6 后台交互要求

- Dashboard：指标卡 + 最近动态 + 系统状态摘要；
- Content Management：搜索、筛选、状态徽标、预览、发布 / 重试快捷操作；
- Subscribers：搜索、排序、状态筛选；
- Workflow Monitor：按内容和阶段查看运行记录，并提供时间线 / 日志视图；
- Manual Publish：同时支持 URL 导入与纯手工录入，并允许填写原文 / 译文字段。

### 5.7 部署与配置加载

#### 配置加载方案

- Django 本身不强制 `.env` 方案，但完全支持通过环境变量读取配置；
- 推荐统一采用：
  - **本地开发**：`.env` 文件
  - **Docker / K8s**：容器环境变量注入
- 实现层建议使用 **django-environ** 或等价方案，在 `settings.py` 中统一读取配置。

#### 推荐加载顺序

- 推荐优先级：
  1. 运行时环境变量
  2. 本地 `.env`
  3. `settings.py` 中的默认值

- 这样可以保证：
  - 本地开发直接维护 `.env`
  - Docker 与 K8s 不依赖 `.env` 文件挂载
  - 配置注入方式在各环境下保持一致

#### 本地运行

- 本地开发目录下提供 `.env.example`，开发者复制为 `.env` 使用；
- 典型配置包括：
  - `DJANGO_SECRET_KEY`
  - `DJANGO_DEBUG`
  - `DJANGO_ALLOWED_HOSTS`
  - `DATABASE_URL`
  - `REDIS_URL`
  - `COS_SECRET_ID`
  - `COS_SECRET_KEY`
  - `COS_BUCKET`
  - `COS_REGION`
  - `GA_MEASUREMENT_ID`
  - `ASR_PROVIDER=mimo`
  - `ASR_API_BASE_URL=https://api.xiaomimimo.com/v1`
  - `MIMO_API_KEY`
  - `ASR_MODEL=mimo-v2.5-asr`
  - `ASR_LANGUAGE_DEFAULT=en`
  - `ASR_TIMEOUT_SECONDS=120`
  - `ASR_MAX_AUDIO_MINUTES=45`
  - `INITIAL_ADMIN_USERNAME`
  - `INITIAL_ADMIN_PASSWORD`
  - `INITIAL_ADMIN_EMAIL`

#### Docker 打包

- Docker 镜像中不内置真实 `.env`；
- 本地或测试环境可通过：
  - `docker run --env-file .env ...`
  - 或 `docker compose` 的 `env_file`
- 镜像本身只包含代码与依赖，配置在启动时注入。

#### Kubernetes 部署

- K8s 中不建议依赖 `.env` 文件本身；
- 推荐通过：
  - `ConfigMap` 注入非敏感配置
  - `Secret` 注入敏感配置
  - `envFrom` 或 `env` 映射到 Pod 环境变量
- Django 启动后仍按同一套 settings 读取环境变量，不需要为 K8s 单独写一套配置逻辑。

#### 推荐部署形态

- **本地开发**
  - Django Web
  - Celery Worker
  - Celery Beat
  - PostgreSQL / Redis 可连接本地或外部实例
- **Docker / K8s**
  - `web` Deployment：Django + Wagtail
  - `worker` Deployment：Celery Worker
  - `beat` Deployment：Celery Beat
  - `ingress` / `gateway`：承接 `www` 与 `admin` 子域名

#### 配置设计原则

- 所有配置都应可由环境变量覆盖；
- `.env` 只作为本地开发便利机制，不作为生产配置载体；
- 敏感信息不写入镜像、不提交仓库；
- 初始管理员自动注入逻辑仅消费环境变量，不依赖手工 SQL。

### 5.8 日志方案

#### 日志分类

- **应用日志**：Django / Wagtail 业务日志，记录页面请求、后台操作、发布动作、配置初始化等；
- **任务日志**：Celery Worker / Beat 日志，记录 discover、fetch、extract、translate、research、notify 等阶段执行情况；
- **集成日志**：调用外部服务时的请求结果摘要，如来源站点抓取、邮件发送、微信草稿、COS 上传；
- **访问日志**：反向代理或 Ingress 的访问日志，用于统计请求状态、来源 IP、耗时与基础审计。

#### 日志格式

- 推荐统一使用 **结构化 JSON 日志**；
- 本地开发允许使用更易读的 console 文本日志，但字段语义应与 JSON 日志保持一致；
- 推荐字段：
  - `timestamp`
  - `level`
  - `logger`
  - `message`
  - `env`
  - `service`（如 `web` / `worker` / `beat`）
  - `request_id`
  - `run_id`
  - `content_item_id`
  - `stage`
  - `source`
  - `path`
  - `method`
  - `status_code`
  - `duration_ms`
  - `error_code`
  - `exception`

- 字段使用建议：
  - Web 请求链路优先带 `request_id`；
  - 工作流任务优先带 `run_id`、`content_item_id`、`stage`；
  - 外部集成错误必须带 `error_code` 或等价错误摘要；
  - 不记录敏感信息，如密码、密钥、完整 token、完整邮件正文。

#### 推荐日志格式示例

```json
{
  "timestamp": "2026-06-03T12:00:00Z",
  "level": "INFO",
  "logger": "techbrief.pipeline",
  "service": "worker",
  "message": "stage completed",
  "env": "prod",
  "run_id": "run_01JXYZ...",
  "content_item_id": "c1c78b6e-8d3b-4ad2-b6c7-2ec9e5f20abc",
  "stage": "extract",
  "duration_ms": 842
}
```

#### 日志级别约定

- `DEBUG`：仅本地开发和问题排查使用；
- `INFO`：常规业务节点、任务完成、发布成功、配置加载成功；
- `WARNING`：可恢复异常、降级路径、重试前失败；
- `ERROR`：任务失败、外部集成调用失败、人工介入必需的问题；
- `CRITICAL`：应用无法启动、数据库不可用、关键配置缺失。

#### 日志与业务追踪的关系

- 结构化日志用于运行时排查；
- `RunLog` 用于业务可视化、后台追踪和失败重试；
- 两者互补：
  - `RunLog` 保存阶段事实；
  - 应用日志保存更细的运行上下文与异常细节。

#### 日志输出策略

- **本地开发**
  - Django / Celery 同时输出到控制台；
  - 可选输出到本地文件目录，如 `./logs/`
- **Docker / Kubernetes**
  - 推荐输出到 `stdout/stderr`；
  - 由容器运行时、日志采集系统或云平台统一收集；
  - 不建议在容器内长期写业务日志文件作为主方案。

#### 日志轮转

- **本地开发 / 非容器部署**
  - 使用 Python `RotatingFileHandler` 或 `TimedRotatingFileHandler`
  - 推荐策略：
    - `app.log`：按大小轮转，单文件 `50MB`，保留 `10` 份
    - `worker.log`：按大小轮转，单文件 `50MB`，保留 `10` 份
    - `beat.log`：按大小轮转，单文件 `20MB`，保留 `5` 份
- **Docker / Kubernetes**
  - 应用只写标准输出，不在应用层做文件轮转；
  - 轮转交由 Docker logging driver、container runtime、Fluent Bit、Loki、ELK 或云日志服务处理；
  - 技术方案层面默认约定：
    - 容器内不持久化业务日志文件
    - 日志采集系统负责 retention 和 rotation

#### 推荐实现口径

- Django 使用 `LOGGING` 配置统一管理；
- Web、Worker、Beat 分别使用独立 logger 名称：
  - `techbrief.web`
  - `techbrief.worker`
  - `techbrief.beat`
  - `techbrief.integrations`
- 通过 middleware 为每个请求生成 `request_id`；
- Celery 任务启动时生成或继承 `run_id`，并贯穿任务日志；
- 应用日志格式在本地与生产保持字段一致，只调整输出样式和 handler。

### 5.9 请求、链路追踪与上下文传播

#### 目标

- 让一次用户请求、一次后台操作、一次定时任务和一条内容处理链路都能被追踪；
- 让日志、`RunLog`、数据库记录和外部集成调用之间可以相互关联；
- 在不引入复杂分布式追踪平台的前提下，建立一套轻量、稳定、可落地的上下文传播规范。

#### 核心追踪字段

- `request_id`
  - 标识一次 Web 请求或后台 HTTP 请求；
  - 由 Django middleware 在请求入口生成；
  - 若上游反向代理已传入 `X-Request-ID`，则优先复用。
- `run_id`
  - 标识一次工作流运行实例；
  - 用于串联 discover、fetch、extract、translate、research、notify 等任务阶段；
  - 由调度入口或人工触发入口生成。
- `content_item_id`
  - 标识具体内容对象；
  - 用于串联单篇文章/视频的抓取、抽取、翻译、发布与对象存储 artifacts。
- `stage`
  - 标识当前执行阶段，如 `discover`、`fetch`、`extract`、`translate`、`publish`。
- `triggered_by`
  - 标识触发来源，如 `scheduler`、`admin_user`、`system_retry`。

#### 生成与传播规则

- **Web 请求入口**
  - Django middleware 生成或继承 `request_id`；
  - 将 `request_id` 放入 request context、日志 context 和响应头 `X-Request-ID`。
- **后台操作触发任务**
  - 若管理员在后台点击“重试 / 发布 / 创建草稿”，则复用当前 `request_id`；
  - 同时生成新的 `run_id` 或复用已有 `run_id`，并将二者一起传入 Celery task。
- **定时任务入口**
  - Beat 触发的任务没有 `request_id`，但必须生成 `run_id`；
  - 由 `run_id` 串联整个任务链。
- **任务链内部**
  - Celery 子任务必须显式接收并继续传递：
    - `run_id`
    - `content_item_id`
    - `stage`
    - `request_id`（如存在）
- **外部集成调用**
  - 对邮件、微信、抓取源、COS 等调用，日志中应带上 `run_id`、`content_item_id`；
  - HTTP 请求如可加自定义 header，可附带：
    - `X-Request-ID`
    - `X-Run-ID`

#### 上下文存放位置

- **日志上下文**
  - 通过 logging filter / contextvars 注入 `request_id`、`run_id`、`content_item_id`、`stage`
- **数据库**
  - `RunLog` 保存：
    - `run_id`
    - `content_item_id`
    - `stage`
    - `outcome`
    - `error_summary`
  - `PublishRecord` 保存：
    - `content_item_id`
    - `channel`
    - `triggered_by`
    - `external_id`
- **Celery task payload**
  - 作为显式参数传递，不依赖隐式全局变量
- **HTTP 响应头**
  - Web 与后台接口建议返回 `X-Request-ID`

#### 推荐追踪关系

```text
request_id -> 一次用户/管理员 HTTP 请求
run_id -> 一次工作流执行实例
content_item_id -> 一条内容对象
stage -> 该内容当前执行阶段
```

- 同一个 `request_id` 可以触发一个或多个 `run_id`
- 同一个 `run_id` 可以覆盖一个或多个 `stage`
- 同一个 `content_item_id` 会在多个 `run_id` 中重复出现，例如首次处理、人工重试、重新发布

#### 与日志和 RunLog 的配合方式

- 日志是细粒度运行上下文；
- `RunLog` 是业务级阶段记录；
- 推荐最小落地规则：
  - 每条 `RunLog` 至少对应一组带相同 `run_id + content_item_id + stage` 的结构化日志；
  - 发生异常时，日志与 `RunLog.error_summary` 应能相互跳转定位。

#### 推荐实现口径

- Django：
  - 使用 middleware 注入 `request_id`
  - 使用 `contextvars` 保存当前请求上下文
- Celery：
  - 在 task 参数中显式传递 `run_id` / `content_item_id` / `request_id`
  - 不依赖线程局部变量跨进程传播上下文
- 数据模型：
  - `RunLog.run_id` 作为主链路追踪键
  - `ContentItem.id` 作为对象级追踪键
- 返回给客户端：
  - Web / Admin 响应头带 `X-Request-ID`
  - 后台错误提示页或日志页可展示 `request_id` / `run_id`

### 5.10 异常处理、错误码与统一 API 返回结构

#### 设计目标

- 让前端、后台页面、Celery 任务和外部集成对错误有统一理解；
- 让日志、`RunLog`、API 响应和数据库错误记录使用同一套错误码语义；
- 保持单人项目可维护，不引入复杂异常框架，但确保错误分类清晰、可检索、可追踪。

#### 异常分类

- **ValidationError**
  - 请求参数缺失、格式非法、状态不允许、字段校验失败
- **NotFoundError**
  - 内容、订阅者、发布记录、运行记录不存在
- **PermissionDeniedError**
  - 未登录、无管理员权限、后台访问被拒绝
- **ConflictError**
  - 幂等冲突、重复发布、状态已变化、重复订阅
- **ExternalServiceError**
  - 来源抓取失败、邮件发送失败、微信接口失败、COS 上传失败
- **PipelineStageError**
  - discover / fetch / extract / translate / research / notify 某一阶段失败
- **SystemError**
  - 数据库不可用、配置缺失、未预期异常

#### 错误码设计

- 推荐格式：
  - `{DOMAIN}_{SCENARIO}`
- 推荐按模块分域：
  - `AUTH_*`
  - `CONTENT_*`
  - `SUBSCRIPTION_*`
  - `WORKFLOW_*`
  - `PIPELINE_*`
  - `INTEGRATION_*`
  - `SYSTEM_*`

- 推荐错误码示例：
  - `AUTH_UNAUTHORIZED`
  - `AUTH_FORBIDDEN`
  - `CONTENT_NOT_FOUND`
  - `CONTENT_STATUS_CONFLICT`
  - `SUBSCRIPTION_ALREADY_ACTIVE`
  - `WORKFLOW_RUN_NOT_FOUND`
  - `PIPELINE_FETCH_FAILED`
  - `PIPELINE_EXTRACT_FAILED`
  - `PIPELINE_TRANSLATE_FAILED`
  - `INTEGRATION_EMAIL_SEND_FAILED`
  - `INTEGRATION_WECHAT_DRAFT_FAILED`
  - `INTEGRATION_COS_UPLOAD_FAILED`
  - `SYSTEM_CONFIG_MISSING`
  - `SYSTEM_INTERNAL_ERROR`

#### HTTP 状态码映射建议

- `200 OK`
  - 查询成功、普通操作成功
- `201 Created`
  - 创建资源成功，如订阅成功、手动录入成功
- `202 Accepted`
  - 已成功接收异步任务，如重试任务已入队、发布任务已触发
- `400 Bad Request`
  - 参数错误、字段校验失败
- `401 Unauthorized`
  - 未登录或认证失败
- `403 Forbidden`
  - 已登录但无权限访问后台资源
- `404 Not Found`
  - 资源不存在
- `409 Conflict`
  - 状态冲突、重复操作、幂等冲突
- `422 Unprocessable Entity`
  - 业务语义合法但当前无法处理，如内容结构不满足发布条件
- `429 Too Many Requests`
  - 主动限流或重试窗口未到
- `500 Internal Server Error`
  - 未预期系统异常
- `502 Bad Gateway` / `503 Service Unavailable`
  - 外部依赖不可用或临时失败

#### 统一 API 返回结构

- 推荐后端 API 统一返回 envelope：

```json
{
  "success": true,
  "code": "OK",
  "message": "success",
  "data": {},
  "meta": {
    "request_id": "req_01JXYZ...",
    "run_id": "run_01JXYZ..."
  }
}
```

- 失败时：

```json
{
  "success": false,
  "code": "PIPELINE_EXTRACT_FAILED",
  "message": "failed to extract structured content",
  "data": null,
  "error": {
    "type": "PipelineStageError",
    "stage": "extract",
    "details": {
      "content_item_id": "c1c78b6e-8d3b-4ad2-b6c7-2ec9e5f20abc"
    }
  },
  "meta": {
    "request_id": "req_01JXYZ...",
    "run_id": "run_01JXYZ..."
  }
}
```

#### 字段约定

- `success`
  - 布尔值，表示请求是否成功
- `code`
  - 机器可读错误码或 `OK`
- `message`
  - 给前端/后台页面展示的简要提示语
- `data`
  - 成功结果；失败时通常为 `null`
- `error`
  - 失败时的结构化错误信息；成功时可省略
- `meta`
  - 公共元数据，至少包含 `request_id`
  - 异步或任务相关接口建议额外包含 `run_id`

#### API 响应与日志 / RunLog 的关系

- API 返回中的 `code` 应与日志中的 `error_code` 对齐；
- `RunLog.error_summary` 保存简要错误摘要；
- 更细错误细节进入结构化日志；
- 后台页面展示用户可理解的信息，避免直接暴露底层异常堆栈。

#### 任务链路异常处理策略

- **可重试错误**
  - 网络超时、临时 5xx、限流、外部接口瞬时失败
  - 处理方式：自动重试 + 指数退避 + 记录 `WARNING/ERROR`
- **不可重试错误**
  - 参数非法、内容不存在、状态冲突、配置缺失
  - 处理方式：直接失败，记录错误码并停止该阶段
- **需要人工介入错误**
  - 抽取结构损坏、翻译结果结构不合法、手工发布条件不满足
  - 处理方式：任务置为失败或待人工处理，后台提供重试入口

#### 推荐实现口径

- Django 视图层统一捕获业务异常并转换为标准 envelope；
- Celery 任务内部统一抛出带 `error_code` 的业务异常；
- 外部集成适配层将第三方错误先映射为内部错误码，再向上抛出；
- 未知异常统一落为：
  - `code = SYSTEM_INTERNAL_ERROR`
  - `type = SystemError`
- 管理后台页面和开放 API 使用同一套错误码体系，只是展示形式不同。

## 6. 需要提前确认的实施前置条件

### 6.1 外部依赖

- Redis 是否允许引入
- 腾讯云 COS 的 Bucket、地域、访问密钥与回源 / 访问策略由谁提供
- 公开域名与后台子域名的 DNS、反向代理和 HTTPS 证书由谁提供
- Google Analytics Measurement ID、域名绑定与 Cookie / 隐私提示策略由谁提供
- 邮件域名与 DNS 配置谁来提供
- 微信公众号账号类型、权限、AppID/AppSecret 是否具备
- 视频来源范围是否只做官方频道，是否需要白名单

### 6.2 业务边界

- 对视频时长是否设置上限
- 无字幕视频是否全部转录，还是按优先级转录
- 研究报告是否站内公开，还是仅后台可见
- 邮件订阅采用直接订阅成功，不引入 double opt-in
- 初始管理员账号是否允许后续在后台修改用户名 / 密码

## 7. 主要风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| 来源站点改版 | 抓取失败 | 来源适配器隔离、raw HTML 留存、人工修正规则 |
| 视频平台限流/变更 | 视频处理失败 | yt-dlp 统一封装、失败重试、平台白名单 |
| 转录成本与耗时偏高 | 队列堆积或 API 费用上升 | 时长限制、优先级队列、API 超时/重试、预算监控，后续再评估自托管 ASR |
| 翻译结构漂移 | 页面质量下降 | block 翻译、结构校验、人工审核 |
| 邮件投递波动 | 订阅体验下降 | provider webhook、失败重发、bounce 状态管理 |
| 微信素材与 HTML 约束 | 草稿创建失败 | 独立 renderer、图片先上传微信、仅后台手动使用 |

## 8. 最终推荐结论

如果目标是尽快交付一个可运行、可运营、可追溯的 TechBrief MVP，推荐采用：

- **Django + Wagtail** 负责公开站点与后台；
- **自有 PostgreSQL + 腾讯云 COS** 负责业务数据与原始大对象存储；
- **Celery + django-celery-beat + Redis** 负责异步处理与调度；
- **Django 默认认证 + 配置驱动的初始管理员注入** 负责后台登录控制；
- **Trafilatura/readability-lxml** 负责文章抽取；
- **yt-dlp + ffmpeg + mimo-v2.5-asr API** 负责视频、字幕、音频与转录；
- **LLM 分块翻译 + 术语表 + 结构校验** 负责中文内容生产；
- **Google Analytics 4** 负责公开站点 UV/PV 与内容访问统计；
- **Resend** 负责邮件订阅与每日汇总；
- **微信草稿 API** 作为后台独立手动发布工具。

这套组合满足当前 PRD 的所有 P0 核心能力，同时保留后续升级路径：

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
- MiMo Speech Recognition: https://platform.xiaomimimo.com/docs/en-US/api/audio/Speech-Recognition
- APScheduler: https://apscheduler.readthedocs.io/en/stable/userguide.html
- Celery Periodic Tasks: https://github.com/celery/celery/blob/main/docs/userguide/periodic-tasks.rst
- django-celery-beat: https://github.com/celery/django-celery-beat
- Resend: https://resend.com/docs/hackathon
- Postmark: https://postmarkapp.com/developer/api/webhooks-api
- WeChat Draft Add API: https://developers.weixin.qq.com/doc/service/api/draftbox/draftmanage/api_draft_add.html
- FFmpeg: https://ffmpeg.org/ffmpeg.html
