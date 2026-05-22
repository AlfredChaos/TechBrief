# Environment Audit

更新时间：2026-05-22

## Repository Snapshot

### Shape
- 当前仓库仅包含需求文档，尚未初始化为可运行的后端工程（无源码、无依赖清单、无测试、无启动入口）。

### Files
- [README.md](file:///workspace/README.md)
- [TechBrief-PRD.md](file:///workspace/TechBrief-PRD.md)

## Runtime & Tooling

### Available
- OS: Linux（CI/非交互环境）
- Git: 仓库已初始化（`.git` 存在）
- Python: 3.14.4（`/root/.pyenv/versions/3.14.4/bin/python`）
- pip: 26.0.1
- uv: 0.11.7

### Missing / Not Yet Defined (Repo-level)
- Python 工程定义：`pyproject.toml` / `requirements.txt` 等不存在
- 依赖锁：不存在（`uv.lock`/`poetry.lock`/`requirements*.txt`）
- 测试框架配置：`pytest.ini`/`tox.ini` 等不存在
- 质量门禁：lint/format/typecheck 工具未定义（ruff/mypy 等均未配置）
- 启动方式：无 `main.py`/`app.py`，无服务框架选择（FastAPI/Flask 等）
- 部署/运行：无 `Dockerfile`/`docker-compose.yml`/CI workflow
- 配置与密钥：无 `.env.example`/配置加载方案；公众号与模型供应商凭据均未落地

## Capability Domains (This Task)

### Needed
- Application Flow：端到端流水线编排（LangGraph DAG + checkpoint + retry）
- Interface / Protocol：对外触发方式（CLI/HTTP）与可观测/重试入口（按 PRD 的 P0/P1 裁剪）
- Data：SQLite（MVP）数据表/索引/去重键/状态机持久化
- Infrastructure：本地启动、环境变量模板、健康检查（后端服务交付必需）
- Documentation：按 SDD/验收闭环输出需求、架构、契约、交付文档
- Test：核心规则与关键路径测试（去重、阶段重试、结构校验、失败可追溯）

### Optional / Later
- Automation：定时巡检（可先用 cron/apscheduler；也可只做手动触发并在后续补齐）
- Migration / Compatibility：SQLite → Postgres（P1+）

### Not Applicable (Current Scope)
- UI / Interaction：项目明确“无前端”，运营后台属于 P1，当前不作为必须产物

## Key External Dependencies (From PRD)
- LLM 翻译供应商：Minimax（用户指定 Token Plan；需确认 Python SDK/REST 端点、鉴权、限流、费用与最佳实践）
- 微信公众号官方 API：
  - 草稿箱（draft/add）
  - 图片/素材上传（media/upload 或 material/add_material 等）
  - access_token 获取与刷新机制
- 来源站点：OpenAI Blog、Anthropic Blog（RSS 或列表页轮询、ETag/Last-Modified）

## Information Gaps (Blocking Before Implementation)
- Minimax 官方 Token Plan 的：
  - API Base URL、鉴权方式、Python 调用方式
  - 推荐模型名/版本（用于翻译）、上下文窗口、速率限制、错误码、重试建议
  - 计费方式与成本控制建议（长文翻译分段策略）
- LangGraph 在 Python 的：
  - checkpoint 持久化实现方式（SQLite/自定义）
  - 节点重试/回滚语义与最佳实践
- 微信公众号 API 的：
  - 草稿创建请求体字段约束（title/author/content/thumb_media_id 等）
  - 图片上传返回字段、素材类型与限制、频控
  - token 失效与刷新策略、错误码（如 40001/42001 等）的处理建议
- 运行形态确认：
  - 是否必须提供 HTTP 服务（例如 FastAPI）还是 CLI 即可满足 MVP
  - Scheduler 是否属于 MVP 必须（PRD 写“每 2 小时一次”，但可用 cron 外部触发替代）

## Auto-Fix Actions (Safe, Not Yet Executed)
- 初始化 Python 后端工程骨架（建议 uv + `pyproject.toml`），补齐：
  - 依赖与锁文件
  - 测试框架（pytest）
  - lint/format（ruff）
  - 配置加载（dotenv/typed settings）
  - 最小可运行入口（CLI 或 HTTP）
- 建立 `docs/` 目录结构并落地 SDD 产物（需求范围、研究、架构、DAG）

## Manual / Human-in-the-loop Items
- 公众号 AppID/AppSecret、测试号/正式号权限、素材/草稿 API 是否可用（需要人工提供凭据与权限确认）
- Minimax Token/Key 获取与付费计划开通（需要人工提供）
- 若需要访问外网抓取真实博客（OpenAI/Anthropic）且存在网络限制，需要人工确认网络策略

## Current Runnable Commands
- 目前仓库无可运行服务/测试命令（缺少工程文件与源码）。
- 可用的基础环境命令：
  - `python --version`
  - `uv --version`

## Risk Level
- High：当前仓库尚未初始化为工程，且关键外部依赖（Minimax/微信）均需要进一步确认与凭据，必须先补齐调研与工程基座再进入实现阶段。

