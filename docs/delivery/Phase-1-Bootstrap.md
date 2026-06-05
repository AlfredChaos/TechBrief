# Phase 1 Bootstrap Guide

更新时间：2026-06-05

## 1. 目标

当前阶段只交付 Phase 1 工程基座：Django + Wagtail + Celery 项目骨架、配置分层、PostgreSQL/Redis/COS 基础配置、健康检查、统一 JSON 响应、请求链路 ID 与基础日志。

## 2. 目录

- `manage.py`: Django 入口
- `pyproject.toml`: 依赖声明
- `uv.lock`: 依赖锁文件
- `docker-compose.yml`: 本地 PostgreSQL / Redis
- `.env.example`: 本地环境变量模板
- `techbrief/settings/`: `base`、`local`、`production` 分层配置
- `techbrief/health/`: live / ready 健康检查
- `techbrief/api/`: JSON envelope 与错误码基线
- `techbrief/middleware.py`: `X-Request-ID` 注入与 API 错误兜底
- `techbrief/apps/*`: Web、后台、流水线、发布、集成、可观测占位 apps
- 默认本地 Web 端口使用 `8010`，避免与开发机上常见的 `8000` 冲突
- 默认本地 Redis host 端口使用 `6380`，避免与开发机上常驻的 `6379` 冲突

## 3. 本地启动

1. 复制环境变量模板。

```bash
cp .env.example .env
```

2. 启动本地 PostgreSQL 和 Redis。

```bash
docker compose up -d postgres redis
```

3. 安装依赖。

```bash
uv sync
```

4. 执行迁移。

```bash
uv run python manage.py migrate
```

5. 初始化管理员账号。

```bash
uv run python manage.py bootstrap_initial_admin
```

6. 分别启动 Web、Worker、Beat。

```bash
uv run python manage.py runserver 127.0.0.1:8010
uv run celery -A techbrief worker -l info
uv run celery -A techbrief beat -l info
```

## 4. 最小验证

- 根路径 `/` 返回统一 JSON envelope，证明 Django 项目已启动。
- `/cms/` 可访问 Wagtail admin 登录页。
- `/django-admin/` 可访问 Django admin。
- `/health/live/` 返回进程活性。
- `/health/ready/` 会检查数据库、Redis、Celery broker、`django-celery-beat` 表与 COS 配置。

## 5. 健康检查说明

- `live`: 只验证应用进程是否存活。
- `ready`: 验证数据库、Redis 和 Celery broker 是否连通。
- `ready`: 同时验证 `django_celery_beat` 已迁移。
- `ready`: 当 `COS_ENABLED=0` 时，COS 检查会返回 `skipped`；启用后会校验基础配置并初始化 SDK client。

## 6. 响应与日志基线

- API 和健康检查统一使用 `{success, code, message, data, meta}` 响应 envelope。
- 每个请求都会生成或继承 `X-Request-ID`，并回写到响应头。
- 日志默认输出可读文本；设置 `LOG_JSON=1` 后切换为结构化 JSON 日志。
- 错误码当前先提供系统级基线，后续 Task 8-10 再按内容、订阅、工作流、集成域细化。

## 7. 当前限制

- 当前仅完成 Phase 1 工程基座，未开始内容模型、Wagtail 页面模型和业务 API。
- COS 只完成配置和 SDK 初始化基线，未接入实际上传逻辑。
- `ready` 只检查 broker 连通性，不直接判断 worker / beat 进程是否已启动。
