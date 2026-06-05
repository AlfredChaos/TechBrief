# TechBrief

TechBrief 是一个面向 AI 技术内容的公开 Web 站点与后台管理系统。项目采用 Django + Wagtail + Celery 技术栈，已完成 MVP 全部 Phase 1-8 工程实现与 mock-first 验证。

## 当前状态

- **Task 1-11 全部完成**，覆盖文档基线确认、范围锁定、前端保真、数据模型/接口/工作流边界、工程初始化、核心数据模型、公开站点与后台、内容流水线与发布通知、联调验证
- **66 条自动化测试全部通过**，覆盖公开站点、后台管理、内容流水线、发布订阅、前端特性等模块
- **验收清单约 60% 已勾选**，已完成 mock-first 验证与证据沉淀；真实外部集成联调（Resend、微信、COS、ASR）待环境就绪后补充

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | Django + Wagtail |
| 异步任务 | Celery + django-celery-beat + Redis |
| 数据库 | PostgreSQL 16 |
| 对象存储 | 腾讯云 COS |
| 邮件投递 | Resend（当前为 mock） |
| 微信公众号 | 手动草稿工具（当前为 mock） |
| ASR 转录 | mimo-v2.5-asr API（当前为 mock） |
| 包管理 | Python 3.12 + uv |

## MVP 范围

- **公开站点**：首页、列表页、详情页、Archive、About、Privacy、Terms
- **后台管理**：仪表盘、来源管理、订阅者、内容、工作流、手动发布
- **内容类型**：文章 + 公开视频资料
- **核心流程**：发现 → 抓取 → 抽取 → 转录 → 翻译 → 研究 → 审核 → 发布 → 通知
- **邮件**：直接订阅成功、退订、每日汇总
- **微信**：后台手动创建草稿

## 文档导航

### 核心方案

- [PRD](file:///home/shixuan/code/TechBrief/TechBrief-PRD.md)
- [技术方案](file:///home/shixuan/code/TechBrief/docs/delivery/Technical-Solution-Report.md)
- [系统架构](file:///home/shixuan/code/TechBrief/docs/delivery/System-Architecture.md)
- [数据库设计](file:///home/shixuan/code/TechBrief/docs/delivery/Database-Design.md)
- [API 设计](file:///home/shixuan/code/TechBrief/docs/delivery/API-Design.md)

### 交付与验收

- [交付说明](file:///home/shixuan/code/TechBrief/docs/delivery/Delivery-Guide.md)
- [验收清单](file:///home/shixuan/code/TechBrief/docs/delivery/Acceptance-Checklist.md)
- [本地部署与人工验证指南](file:///home/shixuan/code/TechBrief/docs/delivery/Local-Deployment-Verification-Guide.md)
- [Phase 1 启动说明](file:///home/shixuan/code/TechBrief/docs/delivery/Phase-1-Bootstrap.md)
- [Task 11 验证指南](file:///home/shixuan/code/TechBrief/docs/delivery/Task11-Validation-Guide.md)

### 验证证据

- [验收证据目录](file:///home/shixuan/code/TechBrief/docs/validation/task11/)
- [自动化验证脚本](file:///home/shixuan/code/TechBrief/scripts/run_task11_automated_validation.sh)
- [验收报告 JSON](file:///home/shixuan/code/TechBrief/artifacts/validation/task11_acceptance_report.json)

## 快速开始

```bash
# 1. 安装依赖
uv sync

# 2. 启动基础设施
docker compose up -d

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 填入实际值

# 4. 数据库迁移
uv run python manage.py migrate

# 5. 创建管理员
uv run python manage.py bootstrap_initial_admin

# 6. 加载种子数据
uv run python manage.py load_site_seed

# 7. 启动服务
uv run python manage.py runserver                          # Web 服务
uv run celery -A techbrief worker -l info                  # Worker
uv run celery -A techbrief beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler  # Beat
```

详细部署与人工验证步骤请参阅 [本地部署与人工验证指南](file:///home/shixuan/code/TechBrief/docs/delivery/Local-Deployment-Verification-Guide.md)。

## 说明

- 若不同文档之间出现歧义，以最新版本的 PRD、技术方案、数据库设计、API 设计为准
- 早期的阶段性审计与旧实施草案已移除，避免与当前正式方案冲突
