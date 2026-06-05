# TechBrief 本地部署与人工验证指南

本文档提供在本地完整部署 TechBrief MVP 并进行人工端到端验证的步骤。

## 1. 环境要求

| 依赖 | 版本要求 | 说明 |
|------|---------|------|
| Python | >= 3.12 | 推荐使用系统包管理或 pyenv 安装 |
| uv | 最新 | Python 包管理器，[安装方式](https://docs.astral.sh/uv/getting-started/installation/) |
| Docker + Docker Compose | 最新 | 用于启动 PostgreSQL 与 Redis |
| Git | >= 2.0 | 版本控制 |

## 2. 基础设施启动

```bash
# 启动 PostgreSQL 16 与 Redis 7
docker compose up -d

# 验证容器运行状态
docker compose ps
```

预期输出：`postgres` 和 `redis` 两个容器状态为 `running`，端口分别为 `5432` 和 `6379`。

## 3. 项目依赖安装

```bash
cd /path/to/TechBrief

# 安装 Python 依赖（自动创建 .venv 虚拟环境）
uv sync

# 验证安装
uv run python --version  # 应输出 Python 3.12.x
```

## 4. 环境变量配置

```bash
# 复制模板
cp .env.example .env

# 编辑 .env 文件，至少配置以下项：
# - DJANGO_SECRET_KEY（随机字符串，用于加密签名）
# - POSTGRES_*（与 docker-compose.yml 中一致，默认值即可）
# - REDIS_URL（默认 redis://localhost:6379/0）
```

`.env.example` 包含所有可配置项及默认值说明，本地验证阶段 COS、Resend、微信、GA4 等外部服务配置项可留空，系统会自动降级为 mock 模式。

## 5. 数据库初始化

```bash
# 执行数据库迁移
uv run python manage.py migrate

# 创建初始管理员账号
# 默认用户名/密码来自 .env 中的 INITIAL_ADMIN_USERNAME / INITIAL_ADMIN_PASSWORD
uv run python manage.py bootstrap_initial_admin

# 加载 Wagtail 种子页面（首页、About、Privacy、Terms 等静态页）
uv run python manage.py load_site_seed
```

## 6. 启动服务

需要 **3 个终端窗口** 分别运行：

```bash
# 终端 1：Django Web 服务
uv run python manage.py runserver

# 终端 2：Celery Worker（执行异步任务）
uv run celery -A techbrief worker -l info

# 终端 3：Celery Beat（定时调度）
uv run celery -A techbrief beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

## 7. 人工验证清单

### 7.1 公开站点页面

| URL | 预期 | 已验证 |
|-----|------|--------|
| `http://localhost:8000/` | 首页，显示最新内容列表 | |
| `http://localhost:8000/articles` | 文章列表页 | |
| `http://localhost:8000/archive` | 归档页 | |
| `http://localhost:8000/about` | 关于页（静态） | |
| `http://localhost:8000/privacy` | 隐私政策（静态） | |
| `http://localhost:8000/terms` | 使用条款（静态） | |
| `http://localhost:8000/health/live/` | 返回 `{"status": "ok"}` | |
| `http://localhost:8000/health/ready/` | 返回健康检查结果 | |

### 7.2 后台管理

| URL | 预期 | 已验证 |
|-----|------|--------|
| `http://localhost:8000/django-admin/` | Django 后台登录页 | |
| `http://localhost:8000/cms/` | Wagtail CMS 登录页 | |
| `http://localhost:8000/cms/techbrief/` | TechBrief 后台仪表盘 | |
| `http://localhost:8000/cms/techbrief/sources/` | 来源管理页 | |
| `http://localhost:8000/cms/techbrief/content/` | 内容列表页 | |
| `http://localhost:8000/cms/techbrief/subscribers/` | 订阅者列表页 | |
| `http://localhost:8000/cms/techbrief/workflow/` | 工作流执行页 | |

使用步骤 5 中创建的管理员账号登录。

### 7.3 内容流水线验证

```bash
# 手动触发发现任务
uv run python manage.py shell -c "
from techbrief.apps.content_pipeline.tasks import discover_new_items
result = discover_new_items.delay()
print(f'Task ID: {result.id}')
"

# 在后台工作流页面查看任务执行状态与 run log
# 或通过 API 查看：
curl http://localhost:8000/cms/techbrief/api/workflow/ | python -m json.tool
```

### 7.4 订阅与退订链路

```bash
# 通过 API 创建订阅
curl -X POST http://localhost:8000/api/public/subscriptions \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'
# 预期：返回 {"ok": true, "data": {...}}

# 在后台订阅者页面确认记录已创建
# http://localhost:8000/cms/techbrief/subscribers/

# 退订（使用返回的 unsubscribe_token）
curl -X POST http://localhost:8000/api/public/subscriptions/unsubscribe \
  -H "Content-Type: application/json" \
  -d '{"token": "<unsubscribe_token>"}'
```

### 7.5 手动发布验证

1. 登录后台 `http://localhost:8000/cms/techbrief/content/`
2. 点击"手动录入"按钮
3. 填写标题、摘要、正文、来源信息
4. 提交后在内容列表页确认状态为 `review_pending`
5. 点击"发布"操作，确认状态变为 `published`
6. 访问公开首页确认内容已展示

### 7.6 微信草稿验证

1. 登录后台，进入微信发布页
2. 选择已发布内容或手动输入
3. 点击生成草稿
4. 当前为 mock 模式，确认页面显示 `wechat_draft_id` 与成功状态

### 7.7 前端特性验证

| 特性 | 验证方式 | 已验证 |
|------|---------|--------|
| 暗色模式 | 系统切换为暗色主题，页面自动适配 | |
| 阅读进度条 | 滚动详情页，顶部进度条随阅读位置变化 | |
| 浮动订阅按钮 | 详情页右下角显示订阅入口 | |
| 响应式布局 | 缩小浏览器窗口，布局自适应 | |
| 中英双语切换 | 详情页切换阅读模式（中文/双语） | |

## 8. 自动化测试验证

```bash
# 运行全量测试（66 条，使用 SQLite 测试库，不依赖 PostgreSQL）
uv run pytest --tb=short -q

# 运行验收回放验证
uv run python manage.py validate_acceptance_replays --settings=techbrief.settings.test

# 生成验收证据
uv run python manage.py generate_task11_evidence --settings=techbrief.settings.test

# 运行自动化验证脚本
bash scripts/run_task11_automated_validation.sh
```

## 9. 外部集成（可选，需真实凭据）

以下集成在本地验证阶段默认使用 mock，如需真实联调需配置对应凭据：

| 集成 | 环境变量 | 说明 |
|------|---------|------|
| 腾讯云 COS | `COS_BUCKET`, `COS_REGION`, `COS_SECRET_ID`, `COS_SECRET_KEY` | 对象存储，保存原始 HTML/音频/图片 |
| Resend 邮件 | `RESEND_API_KEY`, `EMAIL_FROM_ADDRESS` | 邮件投递，需先完成域名校验 |
| 微信公众号 | `WECHAT_APP_ID`, `WECHAT_APP_SECRET` | 草稿创建，需服务号权限 |
| GA4 | `GA4_MEASUREMENT_ID`, `GA4_API_SECRET` | 流量统计 |
| ASR | `MIMO_ASR_API_KEY` | mimo-v2.5-asr 音频转录 |

## 10. 常见问题

**Q: `uv sync` 报错找不到 Python 3.12**
A: 安装 Python 3.12 或使用 `uv python install 3.12`

**Q: 数据库连接失败**
A: 确认 Docker 容器已启动：`docker compose ps`，检查 `.env` 中数据库配置与 `docker-compose.yml` 一致

**Q: Celery Worker 无响应**
A: 确认 Redis 已启动，检查 `REDIS_URL` 配置正确

**Q: 静态页面 404**
A: 执行 `uv run python manage.py load_site_seed` 加载种子数据

**Q: 测试运行报错 `test.sqlite3`**
A: 该文件为 pytest 自动生成的测试库，已被 `.gitignore` 忽略，无需手动管理
