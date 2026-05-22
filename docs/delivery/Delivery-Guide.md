# TechBrief MVP 交付说明（运行与验收）

更新时间：2026-05-22

## 1. 交付范围（MVP）

- 两个来源：OpenAI Blog、Anthropic Blog
- 端到端流水线：Discover → Fetch → Extract → Translate（Minimax）→ FormatForWeChat → CreateDraft
- 存储：SQLite（单机、单用户）
- 运行形态：CLI + HTTP 服务
- 公众号能力：提供完整适配层；在无真实凭据场景下提供本地 mock（可端到端回放验收）

## 2. 运行形态约定

### 2.1 CLI

预期提供命令（示例，最终以实现为准）：

- `techbrief discover`：执行一次发现（RSS 或列表页轮询）
- `techbrief run`：对队列中待处理文章执行端到端流水线
- `techbrief replay --source openai --urls <...>`：对指定历史文章 URL 做回放处理（用于验收）
- `techbrief retry --article-id <id> [--from-stage extract|translate|format|draft]`：从失败点重试

### 2.2 HTTP 服务

预期提供最小接口（示例，最终以实现为准）：

- `POST /runs/discover`：触发一次发现
- `POST /runs/process`：触发一次处理（可包含批量/并发上限）
- `GET /articles`：按状态分页查询
- `GET /articles/{id}`：查看处理详情（含阶段耗时与错误摘要）
- `POST /articles/{id}/retry`：从失败点重试

## 3. 配置与密钥

### 3.1 Minimax（翻译）

- `MINIMAX_API_KEY`：Minimax Key
- `MINIMAX_BASE_URL`：API Base URL
- `MINIMAX_MODEL`：用于翻译的模型标识
- `TRANSLATION_STYLE`：中文风格（默认直译风）
- `GLOSSARY_PATH`：术语表路径（YAML/JSON）

### 3.2 微信公众号（草稿/素材）

本次交付默认支持 mock 模式；真实接入可后续补齐。

- `WECHAT_MODE`：`mock` 或 `real`（默认 `mock`）
- `WECHAT_APP_ID`、`WECHAT_APP_SECRET`：真实模式必填
- `WECHAT_TOKEN_CACHE_PATH`：token 缓存文件（真实模式）

### 3.3 存储与运行

- `DATABASE_URL`：SQLite 文件路径（默认 `sqlite:///./data/techbrief.db`）
- `DATA_DIR`：raw_html、图片等临时/持久化数据目录

## 4. Mock 策略（无公众号凭据场景）

### 4.1 草稿创建 mock

- `CreateDraft` 在 mock 模式下返回可追踪的 `wechat_draft_id`
- 草稿内容（标题/正文 HTML/素材引用）保存到本地目录，便于验收时人工查看
- 失败注入：可通过参数或环境变量模拟微信接口错误码，用于验证重试与可追溯能力

### 4.2 图片上传 mock

- 下载原图并计算内容 hash
- 生成 mock 的可访问 URL（本地路径或本地静态服务地址），并替换正文 `img src`

## 5. 验收回放流程（建议）

按 [Acceptance-Checklist.md](file:///workspace/docs/delivery/Acceptance-Checklist.md) 逐项勾选：

1) 准备 10 篇回放 URL（OpenAI 5 篇 + Anthropic 5 篇）
2) 运行回放命令，生成每篇文章的：
   - raw_html
   - content_ast / content_md
   - zh_ast / zh_md
   - wechat_html
   - wechat_draft_id（mock）
3) 抽样检查结构保真：标题层级、代码块数量、主要图片存在
4) 验证去重：对同一批 URL 重复执行，不产生第二份草稿
5) 人为注入失败（翻译/排版/草稿创建），验证：
   - 错误阶段与摘要可查询
   - 从失败点重试后成功
6) 检查文末模板固定区块在草稿内容中出现且字段正确

