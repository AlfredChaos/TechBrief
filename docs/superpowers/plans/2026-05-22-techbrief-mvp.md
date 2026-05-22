# TechBrief MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable TechBrief MVP that discovers OpenAI/Anthropic blog posts, translates them to Chinese, formats for WeChat, and creates drafts via a local mock adapter with resumable stages and traceability.

**Architecture:** A stage-based pipeline persists state and artifacts in SQLite, enabling per-article retries from a failed stage. A CLI and a minimal HTTP API both call the same core pipeline services, while external integrations (Minimax, WeChat) are behind adapters with mock-first defaults.

**Tech Stack:** Python 3.14, uv, httpx, trafilatura, PyYAML, FastAPI, Typer, pytest, ruff, SQLite (stdlib sqlite3)

---

## File Structure

- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `src/techbrief/__init__.py`
- Create: `src/techbrief/config.py`
- Create: `src/techbrief/db.py`
- Create: `src/techbrief/models.py`
- Create: `src/techbrief/sources/__init__.py`
- Create: `src/techbrief/sources/openai.py`
- Create: `src/techbrief/sources/anthropic.py`
- Create: `src/techbrief/fetch.py`
- Create: `src/techbrief/extract.py`
- Create: `src/techbrief/glossary.py`
- Create: `src/techbrief/translate/__init__.py`
- Create: `src/techbrief/translate/minimax.py`
- Create: `src/techbrief/format_wechat.py`
- Create: `src/techbrief/wechat/__init__.py`
- Create: `src/techbrief/wechat/mock.py`
- Create: `src/techbrief/wechat/real.py`
- Create: `src/techbrief/pipeline.py`
- Create: `src/techbrief/cli.py`
- Create: `src/techbrief/api.py`
- Create: `tests/test_dedupe.py`
- Create: `tests/test_pipeline_retry.py`
- Create: `tests/test_translate_glossary.py`
- Create: `tests/test_format_wechat.py`

---

### Task 1: Initialize Python Project Baseline

**Files:**
- Create: `pyproject.toml`
- Create: `src/techbrief/__init__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "techbrief"
version = "0.1.0"
requires-python = ">=3.14"
dependencies = [
  "httpx>=0.27.0",
  "trafilatura>=1.8.0",
  "PyYAML>=6.0.1",
  "pydantic>=2.7.0",
  "pydantic-settings>=2.2.1",
  "fastapi>=0.110.0",
  "uvicorn>=0.27.1",
  "typer>=0.12.3",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0.0",
  "ruff>=0.4.0",
]

[tool.ruff]
line-length = 100
target-version = "py314"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create package init**

```python
__all__ = []
```

- [ ] **Step 3: Verify environment**

Run: `uv --version`
Expected: prints uv version

- [ ] **Step 4: Install dependencies**

Run: `uv sync --all-extras`
Expected: dependency resolution completes without error

- [ ] **Step 5: Run tests (empty)**

Run: `uv run pytest -q`
Expected: `no tests ran` (exit code 0 once tests exist; for now it may say 0 tests)

---

### Task 2: Configuration, Environments, and Output Directories

**Files:**
- Create: `.env.example`
- Create: `src/techbrief/config.py`

- [ ] **Step 1: Create .env.example**

```dotenv
DATABASE_URL=sqlite:///./data/techbrief.db
DATA_DIR=./data

GLOSSARY_PATH=./glossary.yml
TRANSLATION_STYLE=literal

MINIMAX_BASE_URL=
MINIMAX_API_KEY=
MINIMAX_MODEL=

WECHAT_MODE=mock
WECHAT_APP_ID=
WECHAT_APP_SECRET=
WECHAT_TOKEN_CACHE_PATH=./data/wechat_token.json

MOCK_OUTPUT_DIR=./data/mock_wechat
```

- [ ] **Step 2: Implement Settings**

```python
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/techbrief.db"
    data_dir: str = "./data"

    glossary_path: str = "./glossary.yml"
    translation_style: str = "literal"

    minimax_base_url: str = ""
    minimax_api_key: str = ""
    minimax_model: str = ""

    wechat_mode: str = "mock"
    wechat_app_id: str = ""
    wechat_app_secret: str = ""
    wechat_token_cache_path: str = "./data/wechat_token.json"

    mock_output_dir: str = "./data/mock_wechat"


def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 3: Smoke import**

Run: `uv run python -c "from techbrief.config import get_settings; print(get_settings().database_url)"`
Expected: prints default DATABASE_URL

---

### Task 3: Data Model and SQLite Persistence (Articles, Assets, Run Logs)

**Files:**
- Create: `src/techbrief/models.py`
- Create: `src/techbrief/db.py`
- Test: `tests/test_dedupe.py`

- [ ] **Step 1: Write failing dedupe test**

```python
from techbrief.db import Database


def test_dedupe_key_blocks_duplicate(tmp_path):
    db = Database(f"sqlite:///{tmp_path}/t.db")
    db.migrate()

    a1 = db.upsert_article(source="openai", canonical_url="https://example.com/a", url="https://example.com/a")
    a2 = db.upsert_article(source="openai", canonical_url="https://example.com/a", url="https://example.com/a")

    assert a1["id"] == a2["id"]
```

- [ ] **Step 2: Implement models**

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class Stage(StrEnum):
    discovered = "discovered"
    fetched = "fetched"
    extracted = "extracted"
    translated = "translated"
    formatted = "formatted"
    drafted = "drafted"
    failed = "failed"


@dataclass(frozen=True)
class RunResult:
    stage: Stage
    ok: bool
    error_code: str | None = None
    error_message: str | None = None
    details: dict[str, Any] | None = None
```

- [ ] **Step 3: Implement SQLite Database**

```python
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Database:
    def __init__(self, database_url: str):
        if not database_url.startswith("sqlite:///"):
            raise ValueError("Only sqlite:/// URLs are supported in MVP")
        self._path = Path(database_url.removeprefix("sqlite:///"))
        _ensure_parent(self._path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def migrate(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS articles (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  source TEXT NOT NULL,
                  url TEXT NOT NULL,
                  canonical_url TEXT NOT NULL,
                  dedupe_key TEXT NOT NULL UNIQUE,
                  title TEXT,
                  author TEXT,
                  published_at TEXT,
                  status TEXT NOT NULL,
                  raw_html_path TEXT,
                  content_ast_json TEXT,
                  zh_ast_json TEXT,
                  wechat_html TEXT,
                  wechat_draft_id TEXT,
                  last_error_stage TEXT,
                  last_error_code TEXT,
                  last_error_message TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS run_logs (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  article_id INTEGER NOT NULL,
                  stage TEXT NOT NULL,
                  started_at TEXT NOT NULL,
                  ended_at TEXT NOT NULL,
                  outcome TEXT NOT NULL,
                  error_summary TEXT,
                  FOREIGN KEY(article_id) REFERENCES articles(id)
                )
                """
            )

    def upsert_article(self, *, source: str, url: str, canonical_url: str) -> dict[str, Any]:
        dedupe_key = _sha256(f"{source}:{canonical_url}")
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM articles WHERE dedupe_key = ?", (dedupe_key,)).fetchone()
            if row is not None:
                return dict(row)
            conn.execute(
                """
                INSERT INTO articles (
                  source, url, canonical_url, dedupe_key, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (source, url, canonical_url, dedupe_key, "discovered", now, now),
            )
            row = conn.execute("SELECT * FROM articles WHERE dedupe_key = ?", (dedupe_key,)).fetchone()
            if row is None:
                raise RuntimeError("Failed to insert article")
            return dict(row)

    def update_article(self, article_id: int, **fields: Any) -> None:
        now = datetime.now(timezone.utc).isoformat()
        keys = list(fields.keys()) + ["updated_at"]
        values = list(fields.values()) + [now]
        sets = ", ".join([f"{k} = ?" for k in keys])
        with self._connect() as conn:
            conn.execute(f"UPDATE articles SET {sets} WHERE id = ?", (*values, article_id))

    def get_article(self, article_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
            return None if row is None else dict(row)

    def list_articles(self, status: str | None = None, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if status is None:
                rows = conn.execute(
                    "SELECT * FROM articles ORDER BY id DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM articles WHERE status = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                    (status, limit, offset),
                ).fetchall()
            return [dict(r) for r in rows]

    def append_run_log(
        self,
        *,
        article_id: int,
        stage: str,
        started_at: str,
        ended_at: str,
        outcome: str,
        error_summary: str | None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO run_logs (article_id, stage, started_at, ended_at, outcome, error_summary)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (article_id, stage, started_at, ended_at, outcome, error_summary),
            )

    def set_json_field(self, article_id: int, field: str, value: Any) -> None:
        self.update_article(article_id, **{field: json.dumps(value, ensure_ascii=False)})
```

- [ ] **Step 4: Run dedupe test**

Run: `uv run pytest -q tests/test_dedupe.py::test_dedupe_key_blocks_duplicate`
Expected: PASS

---

### Task 4: Discover (OpenAI/Anthropic RSS or List Polling)

**Files:**
- Create: `src/techbrief/sources/openai.py`
- Create: `src/techbrief/sources/anthropic.py`
- Modify: `pyproject.toml` (add `feedparser>=6.0.11`)

- [ ] **Step 1: Add dependency**

```toml
dependencies = [
  "feedparser>=6.0.11",
  "httpx>=0.27.0",
  "trafilatura>=1.8.0",
  "PyYAML>=6.0.1",
  "pydantic>=2.7.0",
  "pydantic-settings>=2.2.1",
  "fastapi>=0.110.0",
  "uvicorn>=0.27.1",
  "typer>=0.12.3",
]
```

- [ ] **Step 2: Implement discoverers**

```python
from __future__ import annotations

from dataclasses import dataclass

import feedparser
import httpx


@dataclass(frozen=True)
class DiscoveredItem:
    source: str
    url: str
    canonical_url: str


def discover_from_rss(*, source: str, rss_url: str) -> list[DiscoveredItem]:
    parsed = feedparser.parse(rss_url)
    items: list[DiscoveredItem] = []
    for e in parsed.entries:
        url = getattr(e, "link", None)
        if not url:
            continue
        items.append(DiscoveredItem(source=source, url=url, canonical_url=url))
    return items


def fetch_with_conditional(
    client: httpx.Client,
    url: str,
    *,
    etag: str | None = None,
    last_modified: str | None = None,
) -> httpx.Response:
    headers: dict[str, str] = {}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    return client.get(url, headers=headers, follow_redirects=True, timeout=30)
```

---

### Task 5: Fetch (raw_html persistence)

**Files:**
- Create: `src/techbrief/fetch.py`

- [ ] **Step 1: Implement fetcher**

```python
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import httpx


def store_raw_html(*, data_dir: str, article_id: int, html: str) -> str:
    base = Path(data_dir) / "raw_html"
    base.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = base / f"{article_id}_{ts}.html"
    path.write_text(html, encoding="utf-8")
    return str(path)


def fetch_html(client: httpx.Client, url: str) -> str:
    r = client.get(url, follow_redirects=True, timeout=60)
    r.raise_for_status()
    return r.text
```

---

### Task 6: Extract (HTML → AST + metadata)

**Files:**
- Create: `src/techbrief/extract.py`

- [ ] **Step 1: Implement minimal AST**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import trafilatura


NodeType = Literal[
    "h1",
    "h2",
    "h3",
    "h4",
    "p",
    "ul",
    "ol",
    "li",
    "blockquote",
    "code_block",
    "image",
    "hr",
]


@dataclass
class Node:
    type: NodeType
    text: str | None = None
    lang: str | None = None
    url: str | None = None
    children: list["Node"] | None = None


def extract_main_text(html: str) -> str:
    extracted = trafilatura.extract(html, include_links=True, include_images=True)
    if not extracted:
        raise ValueError("extract_failed")
    return extracted
```

---

### Task 7: Glossary Application + Translation Adapter (Minimax)

**Files:**
- Create: `src/techbrief/glossary.py`
- Create: `src/techbrief/translate/minimax.py`
- Test: `tests/test_translate_glossary.py`

- [ ] **Step 1: Write glossary test**

```python
from techbrief.glossary import apply_glossary


def test_apply_glossary_replaces_terms():
    glossary = {"function calling": "函数调用", "token": "Token"}
    out = apply_glossary("Use function calling with a token.", glossary)
    assert "函数调用" in out
    assert "Token" in out
```

- [ ] **Step 2: Implement glossary**

```python
from __future__ import annotations

import re
from typing import Any

import yaml


def load_glossary(path: str) -> dict[str, str]:
    data: Any = yaml.safe_load(open(path, "r", encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in data.items():
        if isinstance(k, str) and isinstance(v, str):
            out[k] = v
    return out


def apply_glossary(text: str, glossary: dict[str, str]) -> str:
    out = text
    for src, dst in glossary.items():
        out = re.sub(re.escape(src), dst, out, flags=re.IGNORECASE)
    return out
```

- [ ] **Step 3: Implement Minimax translator (HTTP, mockable)**

```python
from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class MinimaxConfig:
    base_url: str
    api_key: str
    model: str


class MinimaxTranslator:
    def __init__(self, cfg: MinimaxConfig, client: httpx.Client):
        self._cfg = cfg
        self._client = client

    def translate(self, *, text: str) -> str:
        if not self._cfg.base_url or not self._cfg.api_key or not self._cfg.model:
            raise ValueError("minimax_config_missing")
        r = self._client.post(
            f"{self._cfg.base_url.rstrip('/')}/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._cfg.api_key}"},
            json={
                "model": self._cfg.model,
                "messages": [
                    {"role": "system", "content": "Translate to Simplified Chinese, keep code blocks unchanged."},
                    {"role": "user", "content": text},
                ],
                "temperature": 0.2,
            },
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        if not isinstance(content, str) or not content.strip():
            raise ValueError("minimax_empty_response")
        return content
```

- [ ] **Step 4: Run glossary test**

Run: `uv run pytest -q tests/test_translate_glossary.py::test_apply_glossary_replaces_terms`
Expected: PASS

---

### Task 8: WeChat HTML Formatter (AST → HTML)

**Files:**
- Create: `src/techbrief/format_wechat.py`
- Test: `tests/test_format_wechat.py`

- [ ] **Step 1: Write formatter test**

```python
from techbrief.format_wechat import format_wechat_html


def test_format_wechat_html_emits_basic_tags():
    ast = [
        {"type": "h2", "text": "Title"},
        {"type": "p", "text": "Hello"},
        {"type": "code_block", "text": "print(1)", "lang": "python"},
    ]
    html = format_wechat_html(ast, footer_html="<p>Footer</p>")
    assert "<h2>" in html
    assert "<p>" in html
    assert "<pre>" in html
    assert "Footer" in html
```

- [ ] **Step 2: Implement formatter**

```python
from __future__ import annotations

import html
from typing import Any


def format_wechat_html(ast: list[dict[str, Any]], *, footer_html: str) -> str:
    parts: list[str] = []
    for n in ast:
        t = n.get("type")
        if t in {"h1", "h2", "h3", "h4"}:
            parts.append(f"<{t}>{html.escape(n.get('text', '') or '')}</{t}>")
        elif t == "p":
            parts.append(f"<p>{html.escape(n.get('text', '') or '')}</p>")
        elif t == "code_block":
            code = n.get("text", "") or ""
            parts.append(f"<pre><code>{html.escape(code)}</code></pre>")
        elif t == "blockquote":
            parts.append(f"<blockquote>{html.escape(n.get('text', '') or '')}</blockquote>")
        elif t == "image":
            src = n.get("url", "") or ""
            parts.append(f'<p><img src="{html.escape(src)}" /></p>')
        elif t == "hr":
            parts.append("<hr/>")
    parts.append(footer_html)
    return "\n".join(parts)
```

- [ ] **Step 3: Run formatter test**

Run: `uv run pytest -q tests/test_format_wechat.py::test_format_wechat_html_emits_basic_tags`
Expected: PASS

---

### Task 9: WeChat Draft Adapter (mock-first) + Local Artifacts

**Files:**
- Create: `src/techbrief/wechat/mock.py`
- Create: `src/techbrief/wechat/real.py`

- [ ] **Step 1: Implement mock adapter**

```python
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any


class MockWeChatClient:
    def __init__(self, out_dir: str):
        self._dir = Path(out_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def create_draft(self, *, title: str, author: str, html_content: str, assets: list[dict[str, Any]]) -> str:
        draft_id = f"mock_{uuid.uuid4().hex}"
        payload = {
            "draft_id": draft_id,
            "title": title,
            "author": author,
            "content_html": html_content,
            "assets": assets,
        }
        (self._dir / f"{draft_id}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")
        return draft_id
```

- [ ] **Step 2: Implement real adapter (token + draft/add)**

```python
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx


class RealWeChatClient:
    def __init__(self, client: httpx.Client, *, app_id: str, app_secret: str, token_cache_path: str):
        self._client = client
        self._app_id = app_id
        self._app_secret = app_secret
        self._token_cache_path = Path(token_cache_path)

    def _read_cached_token(self) -> str | None:
        if not self._token_cache_path.exists():
            return None
        data = json.loads(self._token_cache_path.read_text("utf-8"))
        token = data.get("access_token")
        expires_at = data.get("expires_at")
        if not isinstance(token, str) or not isinstance(expires_at, str):
            return None
        if datetime.now(timezone.utc) >= datetime.fromisoformat(expires_at):
            return None
        return token

    def _write_cached_token(self, *, access_token: str, expires_in: int) -> None:
        self._token_cache_path.parent.mkdir(parents=True, exist_ok=True)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(0, expires_in - 120))
        payload = {"access_token": access_token, "expires_at": expires_at.isoformat()}
        self._token_cache_path.write_text(json.dumps(payload, ensure_ascii=False), "utf-8")

    def _get_access_token(self) -> str:
        cached = self._read_cached_token()
        if cached:
            return cached
        if not self._app_id or not self._app_secret:
            raise ValueError("wechat_credentials_missing")
        r = self._client.get(
            "https://api.weixin.qq.com/cgi-bin/token",
            params={"grant_type": "client_credential", "appid": self._app_id, "secret": self._app_secret},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        token = data.get("access_token")
        expires_in = data.get("expires_in", 0)
        if not isinstance(token, str) or not token:
            raise ValueError(f"wechat_token_failed:{data.get('errcode')}:{data.get('errmsg')}")
        if not isinstance(expires_in, int):
            expires_in = 0
        self._write_cached_token(access_token=token, expires_in=expires_in)
        return token

    def create_draft(self, *, title: str, author: str, html_content: str, assets: list[dict[str, Any]]) -> str:
        token = self._get_access_token()
        r = self._client.post(
            "https://api.weixin.qq.com/cgi-bin/draft/add",
            params={"access_token": token},
            json={
                "articles": [
                    {
                        "title": title,
                        "author": author,
                        "content": html_content,
                    }
                ]
            },
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        draft_id = data.get("media_id")
        if not isinstance(draft_id, str) or not draft_id:
            raise ValueError(f"wechat_draft_failed:{data.get('errcode')}:{data.get('errmsg')}")
        return draft_id
```

---

### Task 10: Pipeline Orchestration + Retry from Failed Stage

**Files:**
- Create: `src/techbrief/pipeline.py`
- Test: `tests/test_pipeline_retry.py`

- [ ] **Step 1: Write retry test (mock-only)**

```python
from techbrief.db import Database
from techbrief.pipeline import Pipeline, PipelineDeps


def test_retry_from_failed_stage(tmp_path):
    db = Database(f"sqlite:///{tmp_path}/t.db")
    db.migrate()

    a = db.upsert_article(source="openai", canonical_url="https://example.com/a", url="https://example.com/a")

    deps = PipelineDeps(
        db=db,
        data_dir=str(tmp_path),
        translate=lambda s: (_ for _ in ()).throw(RuntimeError("boom")),
        format_html=lambda ast: "<p>x</p>",
        create_draft=lambda title, author, html, assets: "mock_1",
    )
    p = Pipeline(deps)

    p.run_article(a["id"])
    after_fail = db.get_article(a["id"])
    assert after_fail is not None
    assert after_fail["status"] == "failed"
    assert after_fail["last_error_stage"] == "translate"

    deps2 = PipelineDeps(
        db=db,
        data_dir=str(tmp_path),
        translate=lambda s: "中文",
        format_html=lambda ast: "<p>x</p>",
        create_draft=lambda title, author, html, assets: "mock_2",
    )
    p2 = Pipeline(deps2)
    p2.retry_from(a["id"], from_stage="translate")

    after = db.get_article(a["id"])
    assert after is not None
    assert after["status"] == "drafted"
    assert after["wechat_draft_id"] == "mock_2"
```

- [ ] **Step 2: Implement Pipeline**

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

import httpx

from techbrief.db import Database
from techbrief.fetch import fetch_html, store_raw_html


@dataclass(frozen=True)
class PipelineDeps:
    db: Database
    data_dir: str
    translate: Callable[[str], str]
    format_html: Callable[[list[dict[str, Any]]], str]
    create_draft: Callable[[str, str, str, list[dict[str, Any]]], str]


class Pipeline:
    def __init__(self, deps: PipelineDeps):
        self._d = deps

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def run_article(self, article_id: int) -> None:
        a = self._d.db.get_article(article_id)
        if a is None:
            raise ValueError("article_not_found")
        try:
            self._fetch(article_id, a)
            self._translate(article_id)
            self._format(article_id)
            self._draft(article_id)
        except Exception as e:
            msg = str(e)[:500]
            self._d.db.update_article(
                article_id,
                status="failed",
                last_error_message=msg,
            )

    def retry_from(self, article_id: int, *, from_stage: str) -> None:
        a = self._d.db.get_article(article_id)
        if a is None:
            raise ValueError("article_not_found")
        self._d.db.update_article(article_id, status=from_stage, last_error_stage=None, last_error_code=None, last_error_message=None)
        if from_stage == "fetch":
            self.run_article(article_id)
            return
        if from_stage == "translate":
            self._translate(article_id)
            self._format(article_id)
            self._draft(article_id)
            return
        if from_stage == "format":
            self._format(article_id)
            self._draft(article_id)
            return
        if from_stage == "draft":
            self._draft(article_id)
            return
        raise ValueError("unsupported_from_stage")

    def _fetch(self, article_id: int, a: dict[str, Any]) -> None:
        started_at = self._now()
        with httpx.Client() as client:
            html = fetch_html(client, a["url"])
        raw_path = store_raw_html(data_dir=self._d.data_dir, article_id=article_id, html=html)
        self._d.db.update_article(article_id, raw_html_path=raw_path, status="fetched")
        self._d.db.append_run_log(
            article_id=article_id,
            stage="fetch",
            started_at=started_at,
            ended_at=self._now(),
            outcome="ok",
            error_summary=None,
        )

    def _translate(self, article_id: int) -> None:
        a = self._d.db.get_article(article_id)
        if a is None or not a.get("raw_html_path"):
            raise ValueError("missing_raw_html")
        started_at = self._now()
        raw_html = open(a["raw_html_path"], "r", encoding="utf-8").read()
        zh = self._d.translate(raw_html)
        self._d.db.update_article(article_id, zh_ast_json=json.dumps([{"type": "p", "text": zh}], ensure_ascii=False), status="translated")
        self._d.db.append_run_log(
            article_id=article_id,
            stage="translate",
            started_at=started_at,
            ended_at=self._now(),
            outcome="ok",
            error_summary=None,
        )

    def _format(self, article_id: int) -> None:
        a = self._d.db.get_article(article_id)
        if a is None or not a.get("zh_ast_json"):
            raise ValueError("missing_zh_ast")
        started_at = self._now()
        ast = json.loads(a["zh_ast_json"])
        html = self._d.format_html(ast)
        self._d.db.update_article(article_id, wechat_html=html, status="formatted")
        self._d.db.append_run_log(
            article_id=article_id,
            stage="format",
            started_at=started_at,
            ended_at=self._now(),
            outcome="ok",
            error_summary=None,
        )

    def _draft(self, article_id: int) -> None:
        a = self._d.db.get_article(article_id)
        if a is None or not a.get("wechat_html"):
            raise ValueError("missing_wechat_html")
        started_at = self._now()
        draft_id = self._d.create_draft(a.get("title") or "Untitled", a.get("author") or "", a["wechat_html"], [])
        self._d.db.update_article(article_id, wechat_draft_id=draft_id, status="drafted")
        self._d.db.append_run_log(
            article_id=article_id,
            stage="draft",
            started_at=started_at,
            ended_at=self._now(),
            outcome="ok",
            error_summary=None,
        )
```

- [ ] **Step 3: Run retry test**

Run: `uv run pytest -q tests/test_pipeline_retry.py::test_retry_from_failed_stage`
Expected: PASS

---

### Task 11: CLI + HTTP API Wiring (shared core)

**Files:**
- Create: `src/techbrief/cli.py`
- Create: `src/techbrief/api.py`

- [ ] **Step 1: Implement CLI (Typer)**

```python
from __future__ import annotations

import typer

from techbrief.config import get_settings
from techbrief.db import Database
from techbrief.format_wechat import format_wechat_html
from techbrief.pipeline import Pipeline, PipelineDeps
from techbrief.wechat.mock import MockWeChatClient

app = typer.Typer()


@app.command()
def migrate() -> None:
    s = get_settings()
    db = Database(s.database_url)
    db.migrate()
    typer.echo("ok")


@app.command()
def retry(article_id: int, from_stage: str = typer.Option("translate")) -> None:
    s = get_settings()
    db = Database(s.database_url)
    db.migrate()
    wc = MockWeChatClient(s.mock_output_dir)
    deps = PipelineDeps(
        db=db,
        data_dir=s.data_dir,
        translate=lambda t: t,
        format_html=lambda ast: format_wechat_html(ast, footer_html=""),
        create_draft=lambda title, author, html, assets: wc.create_draft(title=title, author=author, html_content=html, assets=assets),
    )
    Pipeline(deps).retry_from(article_id, from_stage=from_stage)
    typer.echo("ok")


def main() -> None:
    app()
```

- [ ] **Step 2: Implement HTTP API (FastAPI)**

```python
from __future__ import annotations

from fastapi import FastAPI

from techbrief.config import get_settings
from techbrief.db import Database

app = FastAPI()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/articles")
def list_articles(status: str | None = None, limit: int = 50, offset: int = 0) -> dict[str, object]:
    s = get_settings()
    db = Database(s.database_url)
    db.migrate()
    return {"items": db.list_articles(status=status, limit=limit, offset=offset)}
```

- [ ] **Step 3: Smoke run**

Run: `uv run python -m techbrief.cli migrate`
Expected: prints `ok`

Run: `uv run uvicorn techbrief.api:app --host 127.0.0.1 --port 8000`
Expected: server starts and `/healthz` returns `{"status":"ok"}`

---

## Spec Coverage Self-Review (PRD v0.1)

- P0 全链路：本计划覆盖 Discover/Fetch/Extract/Translate/Format/CreateDraft 的可运行骨架，并以 mock 草稿满足无凭据验收。
- 去重：`dedupe_key = sha256(source + canonical_url)` 已纳入 DB 设计与测试。
- 可追溯/可重试：RunLog 表 + `retry_from` 机制与测试覆盖“从失败点重试后成功”。
- 文末署名：在 `format_wechat_html(..., footer_html=...)` 机制上实现模板注入（后续任务可将 PRD 模板落到配置文件）。

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-22-techbrief-mvp.md`. Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration
2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
