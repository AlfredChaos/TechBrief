# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Summary

TechBrief — bilingual (zh/en) AI tech content aggregation and publishing platform. Django 5.2 monolith with Wagtail 6.4 CMS, Celery async pipeline, PostgreSQL 16, Redis 7. The system discovers, fetches, extracts, transcribes, translates, researches, reviews, publishes, and notifies subscribers about curated tech articles and video content. Currently in MVP stage; all pipeline AI/LLM handlers produce placeholder data.

## Commands

```bash
# Install dependencies
uv sync

# Start infrastructure (PostgreSQL + Redis)
docker compose up -d

# Database setup (first time)
cp .env.example .env          # then edit values
uv run python manage.py migrate
uv run python manage.py bootstrap_initial_admin
uv run python manage.py load_site_seed

# Run dev server
uv run python manage.py runserver

# Run Celery worker + beat scheduler
uv run celery -A techbrief worker -l info
uv run celery -A techbrief beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

# Run all tests (SQLite + LocMemCache + eager Celery — no external services needed)
uv run pytest

# Run a single test file / test
uv run pytest tests/test_models.py
uv run pytest tests/test_models.py::TestCaseName::test_method -v

# Lint and format
uv run ruff check .
uv run ruff format .

# Automated acceptance validation
bash scripts/run_task11_automated_validation.sh
```

## Architecture

### URL Routing (`techbrief/urls.py`)

| Path prefix | App | Description |
|---|---|---|
| `/` | `web` | Public site (home, articles, archive, detail, static pages, subscription API) |
| `/django-admin/` | Django admin | Standard Django admin |
| `/cms/` | Wagtail | Wagtail CMS admin |
| `/cms/techbrief/` | `admin_console` | Custom admin dashboard (registered via Wagtail hook, uses Django CBVs) |
| `/health/live/`, `/health/ready/` | `health` | Liveness and readiness probes |

### Content Pipeline (core workflow)

Stage sequence: `Discover → Fetch → Extract → Transcribe → Translate → Research → Review Pending → Publish → Notify`

- `techbrief/apps/content_pipeline/services.py` — `DiscoveryWorkflowService` (source iteration + content dedup) and `ContentPipelineService` (stage execution, error handling, next-stage enqueue)
- `techbrief/apps/content_pipeline/tasks.py` — one Celery task per pipeline stage, calls `ContentPipelineService.run_stage()`
- Each stage handler is a method on `ContentPipelineService`. **All current handlers produce placeholder/mock data** — real AI/LLM integration is TODO.

### Publishing (`techbrief/apps/publishers/services.py`)

Three main operations: `publish_content_item()` (creates immutable snapshot), `notify_content_item()` (email digest via adapter), `create_wechat_draft()` (WeChat draft API via adapter).

### Integration Adapters (`techbrief/apps/integrations/adapters.py`)

Strategy pattern, selected by env vars:
- `EMAIL_DELIVERY_ADAPTER` → `mock` (default) or `resend`
- `WECHAT_DRAFT_ADAPTER` → `mock` (default) or `wechat_api`

### Django Apps

| App | Responsibility |
|---|---|
| `core` | User model, idempotency keys, base models (UUID pk, `TimeStampedModel`) |
| `content_pipeline` | Source/endpoint management, discovery runs, content items, artifacts, pipeline stages |
| `publishers` | Subscribers, email digest/delivery, publish records, WeChat drafts, content snapshots |
| `integrations` | External service adapters (email, WeChat) |
| `admin_console` | Custom admin UI (~30 CBVs at `/cms/techbrief/`) |
| `web` | Public site with Wagtail pages (HomePage, ListingPage, StaticPage), bilingual support |
| `observability` | RunLog model for pipeline stage execution tracking |
| `health` | DB/Redis/Celery/COS health checks |

### Settings

`techbrief/settings/` — layered config: `base.py` → `local.py` / `test.py` / `production.py`. Test settings swap everything to SQLite + LocMemCache + eager Celery.

### Middleware

- `RequestIdMiddleware` — extracts/generates `X-Request-ID`, sets context vars
- `ApiExceptionMiddleware` — catches `AppError` for API/health routes, returns structured JSON

### Key Design Decisions

- All DB tables prefixed `tb_`. All models use UUID primary keys and `TimeStampedModel` (id, created_at, updated_at).
- `ContentPageSnapshot` provides immutable published state, decoupled from evolving `ContentItem`.
- Content deduplication via SHA-256 hash of source + identity fields.
- Subscription API uses `Idempotency-Key` header with database-backed idempotency protection.
- Admin console is custom Django CBVs registered as a Wagtail menu item (not Wagtail admin views).
- `theme.py` provides Material Design 3 design token system with dark mode support.
- `public_site.py` handles bilingual locale (zh-CN/en-US) via cookie/query/Accept-Language.

## Conventions

- Package manager: `uv` (not pip/poetry). Always use `uv run` to execute commands.
- Linter/formatter: `ruff` (line-length 100, target Python 3.10).
- Test framework: `pytest` with `pytest-django`. Tests live in `/tests/` at project root. Settings module: `techbrief.settings.test`.
- Templates: `templates/<app_name>/` — `web/` for public site, `admin_console/` for admin.
- Logging: structured JSON or text logging via `techbrief/logging_utils.py`, controlled by `JSON_LOGGING` env var.
- Context variables: `techbrief/context.py` — `request_id`, `run_id`, `service` used for correlation across logs.
