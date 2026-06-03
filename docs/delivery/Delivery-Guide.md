# TechBrief MVP 交付说明（Web / Admin / Workflow）

更新时间：2026-06-03

## 1. 交付范围（MVP）

- 两个来源：OpenAI、Anthropic
- 两类内容：公开文章、来自更多公开视频平台的公开视频资料
- 端到端流水线：Discover -> Fetch -> Extract -> TranslateAndResearch -> Review Draft -> Publish Web -> Notify Email
- 产品形态：公开 Web 站点 + 后台管理系统
- 存储：SQLite（单机、单用户 MVP）
- 邮件能力：订阅、退订、每日汇总通知
- 微信公众号能力：后台中的手动草稿创建工具，不属于自动主流程

## 2. 运行形态约定

### 2.1 Web 应用

预期交付两个主要界面：

- 公开站点：首页、列表页、详情页、订阅入口
- 后台管理：仪表盘、订阅者列表、内容列表 / 详情、每日工作流执行页、手动发布页

### 2.2 HTTP 服务

预期至少提供以下接口能力（示例，最终以实现为准）：

- `POST /runs/discover`：触发一次内容发现
- `POST /runs/process`：触发一次处理流水线
- `GET /contents`：分页查询内容列表
- `GET /contents/{id}`：查看内容详情与处理记录
- `POST /contents/{id}/retry`：从失败点重试
- `POST /contents/{id}/publish`：手动发布到 Web
- `GET /subscribers`：查看订阅者列表
- `POST /subscriptions`：创建订阅
- `POST /subscriptions/unsubscribe`：执行退订
- `POST /emails/daily-digest/send`：触发每日汇总邮件任务
- `GET /runs/daily`：查看每日工作流执行情况
- `POST /wechat/drafts`：在后台手动创建公众号草稿

### 2.3 可选 CLI / Job 入口

内部可保留 CLI 或定时任务入口，用于：

- 手动执行 discover / process / replay
- 触发历史数据回放验收
- 调试失败任务与邮件通知任务

## 3. 配置与密钥

### 3.1 翻译服务

- `MINIMAX_API_KEY`：翻译服务 Key
- `MINIMAX_BASE_URL`：API Base URL
- `MINIMAX_MODEL`：翻译模型标识
- `TRANSLATION_STYLE`：中文风格（默认直译风）
- `GLOSSARY_PATH`：术语表路径（YAML / JSON）

### 3.2 邮件服务

- `EMAIL_PROVIDER`：邮件服务供应商标识
- `EMAIL_API_KEY`：邮件服务密钥
- `EMAIL_FROM`：发件地址
- `EMAIL_REPLY_TO`：回复地址（可选）
- `EMAIL_MODE`：`mock` 或 `real`
- `EMAIL_DIGEST_SCHEDULE`：每日汇总发送时间配置

### 3.3 微信公众号（后台手动发布）

- `WECHAT_MODE`：`mock` 或 `real`（默认 `mock`）
- `WECHAT_APP_ID`、`WECHAT_APP_SECRET`：真实模式必填
- `WECHAT_TOKEN_CACHE_PATH`：token 缓存文件

### 3.4 存储与运行

- `DATABASE_URL`：SQLite 文件路径（默认 `sqlite:///./data/techbrief.db`）
- `DATA_DIR`：原始抓取内容、字幕快照、邮件 mock 输出等目录
- `PUBLIC_BASE_URL`：公开站点域名
- `ADMIN_BASE_URL`：后台地址（可与站点同域）

## 4. Mock 策略（无真实凭据场景）

### 4.1 邮件 mock

- 订阅确认邮件、每日汇总邮件写入本地目录
- 保留收件人、主题、正文、触发内容 ID，便于验收
- 支持失败注入，用于验证重发与可追溯能力

### 4.2 微信草稿 mock

- 后台手动创建草稿时返回可追踪的 `wechat_draft_id`
- 草稿默认复用站内内容封面、摘要和作者信息，并将标题、正文、素材引用保存到本地目录，便于人工检查
- 支持模拟接口错误码，验证后台重试流程

## 5. 验收回放流程（建议）

按 [Acceptance-Checklist.md](file:///home/shixuan/code/TechBrief/docs/delivery/Acceptance-Checklist.md) 逐项勾选：

1) 准备 10 条回放内容（OpenAI 5 条 + Anthropic 5 条），其中同时覆盖文章和来自更多公开视频平台的视频资料
2) 运行回放流程，生成每条内容的：
   - 原始 HTML / 文本快照
   - 音频提取结果 / 转录文字稿（针对无字幕视频）
   - content_ast / content_md
   - zh_ast / zh_md
   - 深度研究报告
   - Web 渲染结果或预览页
   - 每日汇总邮件任务记录
3) 抽样检查结构保真：标题层级、代码块数量、主要链接存在
4) 验证去重：对同一批 URL / source_id 重复执行，不产生第二份内容记录
5) 人为注入失败（翻译 / 转录 / 发布 / 邮件发送），验证：
   - 错误阶段与摘要可查询
   - 从失败点重试后成功
6) 通过后台完成：
   - 内容人工发布到 Web
   - 邮箱订阅与退订
   - 查看每日工作流执行记录
   - 验证每日汇总邮件内容
   - 手动创建微信公众号草稿
