# Environment Audit

更新时间：2026-06-03

## Repository Snapshot

### Shape
- 当前仓库仅包含需求与交付文档，尚未初始化为可运行的 Web 工程（无源码、无依赖清单、无测试、无启动入口）。

### Files
- [README.md](file:///home/shixuan/code/TechBrief/README.md)
- [TechBrief-PRD.md](file:///home/shixuan/code/TechBrief/TechBrief-PRD.md)
- [Acceptance-Checklist.md](file:///home/shixuan/code/TechBrief/docs/delivery/Acceptance-Checklist.md)
- [Delivery-Guide.md](file:///home/shixuan/code/TechBrief/docs/delivery/Delivery-Guide.md)

## Runtime & Tooling

### Available
- OS: Linux（CI / 非交互环境）
- Git: 仓库已初始化（`.git` 存在）
- Python: 3.14.4（`/root/.pyenv/versions/3.14.4/bin/python`）
- pip: 26.0.1
- uv: 0.11.7

### Missing / Not Yet Defined (Repo-level)
- Python 工程定义：`pyproject.toml` / `requirements.txt` 等不存在
- 依赖锁：不存在（`uv.lock` / `poetry.lock` / `requirements*.txt`）
- 前端工程定义：无 `package.json`、无前端框架选型、无构建配置
- 测试框架配置：`pytest.ini` / `tox.ini` / 前端测试配置等均不存在
- 质量门禁：lint / format / typecheck 工具未定义（ruff、mypy、eslint 等均未配置）
- 启动方式：无 Web 服务入口、无后台管理入口、无前端开发 / 构建脚本
- 部署 / 运行：无 `Dockerfile` / `docker-compose.yml` / CI workflow
- 配置与密钥：无 `.env.example` / 配置加载方案；翻译、邮件与微信凭据均未落地

## Capability Domains (This Task)

### Needed
- Public Web：公开站点首页、列表页、详情页、订阅入口
- Admin Console：订阅者列表、内容及译文列表、每日工作流执行页、手动发布页
- Workflow：内容发现、抓取、抽取、翻译、审核、发布、邮件通知
- Data：SQLite（MVP）数据表 / 索引 / 去重键 / 状态机持久化
- Integration：翻译服务、邮件服务、微信公众号草稿接口（后台手动）
- Documentation：围绕新 Web 形态补齐需求、架构、交付、验收文档
- Test：核心流程与关键规则测试（去重、失败重试、发布、订阅、通知）

### Optional / Later
- Search / SEO：站内搜索、SEO、专题页
- Media Processing：视频字幕抓取增强、ASR、封面处理
- Migration / Compatibility：SQLite -> Postgres，多用户与角色权限

### Not Applicable (Current Scope)
- 开放式社区能力：评论、互动、用户投稿

## Key External Dependencies (From PRD)
- LLM 翻译供应商：Minimax（或等价供应商）
- 邮件服务供应商：用于订阅、退订和发布通知
- 微信公众号官方 API：仅用于后台手动创建草稿
- 来源站点：OpenAI、Anthropic 的公开文章，以及更多公开视频平台中的相关视频资料页面 / Feed

## Information Gaps (Blocking Before Implementation)
- 翻译供应商：
  - API Base URL、鉴权方式、模型选择、速率限制、错误码、成本控制策略
- 邮件服务：
  - 供应商选型、退订机制、每日汇总模板能力、投递结果回执、频控与合规要求
- 视频资料处理：
  - 多平台来源接入方式、可获取字幕的方式、音频提取与自动转录方案、深度研究报告生成策略
- Web 技术选型：
  - 单体 Web（SSR）还是前后端分离
  - 后台管理与公开站点是否同仓同应用
- 微信公众号手动发布：
  - 草稿创建字段约束、素材接口需求、错误码处理策略
- 调度方案：
  - 内建 scheduler 还是外部 cron / workflow 触发

## Auto-Fix Actions (Safe, Not Yet Executed)
- 初始化 Web 工程骨架，至少补齐：
  - 后端服务框架
  - 前端 / 管理后台框架
  - 数据库与配置加载
  - 测试框架与质量门禁
- 建立围绕公开站点、后台管理、邮件通知、微信手动发布的模块边界
- 将当前文档转化为可执行实施计划与验收脚本

## Manual / Human-in-the-loop Items
- 邮件服务供应商凭据与发件域名配置（需要人工提供）
- 微信公众号 AppID / AppSecret 与接口权限确认（需要人工提供）
- 若需要抓取真实公开网页与视频资料，需要人工确认网络可达性与策略
- 若涉及版权风险更高的内容类型，需要人工确认发布边界

## Current Runnable Commands
- 当前仓库无可运行服务 / 测试命令（缺少工程文件与源码）。
- 可用的基础环境命令：
  - `python --version`
  - `uv --version`

## Risk Level
- High：当前仓库尚未初始化为 Web 工程，且关键外部依赖（翻译、邮件、微信）都需要进一步确认与凭据，必须先补齐技术选型与工程基座再进入实现阶段。
