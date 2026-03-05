# Telegram AI Assistant Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a multi-user Telegram bot that acts as a personal AI assistant with tool use, per-user memory, Google integrations, and a CLI admin tool — deployed as a single Docker container.

**Architecture:** Single asyncio Python process handles Telegram polling, agent execution, OAuth callback, and scheduling. Each user's data lives in an isolated SQLite file and directory. Auth gating on every message via a global SQLite DB.

**Tech Stack:** Python 3.12, Anthropic Agent SDK (`anthropic`), python-telegram-bot 20.x, APScheduler, aiohttp, faster-whisper, pypdf, duckduckgo-search, google-api-python-client, Docker

---

## Task 1: Project Scaffold

**Files:**
- Create: `bot/__init__.py`
- Create: `bot/config.py`
- Create: `requirements.txt`
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Step 1: Write failing test**

```python
# tests/test_config.py
import os
from bot.config import Config

def test_config_loads_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "test_token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test_key")
    monkeypatch.setenv("DATA_DIR", "/tmp/testdata")
    config = Config()
    assert config.telegram_token == "test_token"
    assert config.anthropic_api_key == "test_key"
    assert config.data_dir == "/tmp/testdata"

def test_config_raises_on_missing_required(monkeypatch):
    monkeypatch.delenv("TELEGRAM_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import pytest
    with pytest.raises(ValueError):
        Config()
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_config.py -v
```
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Create `bot/config.py`**

```python
import os
from dataclasses import dataclass

@dataclass
class Config:
    telegram_token: str
    anthropic_api_key: str
    data_dir: str
    google_client_id: str
    google_client_secret: str

    def __init__(self):
        missing = []
        for key in ("TELEGRAM_TOKEN", "ANTHROPIC_API_KEY"):
            if not os.getenv(key):
                missing.append(key)
        if missing:
            raise ValueError(f"Missing required env vars: {', '.join(missing)}")
        self.telegram_token = os.environ["TELEGRAM_TOKEN"]
        self.anthropic_api_key = os.environ["ANTHROPIC_API_KEY"]
        self.data_dir = os.getenv("DATA_DIR", "/data")
        self.google_client_id = os.getenv("GOOGLE_CLIENT_ID", "")
        self.google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
```

**Step 4: Create `requirements.txt`**

```
anthropic>=0.40.0
python-telegram-bot==20.7
aiohttp>=3.9
apscheduler>=3.10
faster-whisper>=1.0
pypdf>=4.0
duckduckgo-search>=6.0
httpx>=0.27
beautifulsoup4>=4.12
wikipedia>=1.4
youtube-transcript-api>=0.6
arxiv>=2.1
feedparser>=6.0
qrcode>=7.4
Pillow>=10.0
google-api-python-client>=2.100
google-auth-oauthlib>=1.2
pytest>=8.0
pytest-asyncio>=0.23
python-dotenv>=1.0
```

**Step 5: Create `Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "bot.main"]
```

**Step 6: Create `docker-compose.yml`**

```yaml
services:
  bot:
    build: .
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./data:/data
    environment:
      - DATA_DIR=/data
```

**Step 7: Create `.env.example`**

```
TELEGRAM_TOKEN=
ANTHROPIC_API_KEY=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
```

**Step 8: Run tests**

```bash
pytest tests/test_config.py -v
```
Expected: PASS

**Step 9: Commit**

```bash
git init
git add .
git commit -m "feat: project scaffold with config and dependencies"
```

---

## Task 2: Database Layer

**Files:**
- Create: `bot/db.py`
- Create: `tests/test_db.py`

**Step 1: Write failing tests**

```python
# tests/test_db.py
import os, tempfile, pytest
from bot.db import GlobalDB, UserDB

@pytest.fixture
def global_db(tmp_path):
    return GlobalDB(str(tmp_path / "global.db"))

@pytest.fixture
def user_db(tmp_path):
    return UserDB(str(tmp_path / "conversations.db"))

def test_global_db_creates_tables(global_db):
    users = global_db.list_users()
    assert users == []

def test_register_user(global_db):
    global_db.register_user(telegram_id=123, username="alice")
    user = global_db.get_user(123)
    assert user["status"] == "pending"
    assert user["is_admin"] == 0

def test_first_user_becomes_admin(global_db):
    global_db.register_user(telegram_id=1, username="first")
    user = global_db.get_user(1)
    assert user["is_admin"] == 1
    assert user["status"] == "approved"

def test_second_user_not_admin(global_db):
    global_db.register_user(telegram_id=1, username="first")
    global_db.register_user(telegram_id=2, username="second")
    user = global_db.get_user(2)
    assert user["is_admin"] == 0
    assert user["status"] == "pending"

def test_approve_user(global_db):
    global_db.register_user(telegram_id=2, username="bob")
    global_db.approve_user(2)
    assert global_db.get_user(2)["status"] == "approved"

def test_ban_user(global_db):
    global_db.register_user(telegram_id=2, username="bob")
    global_db.ban_user(2)
    assert global_db.get_user(2)["status"] == "banned"

def test_user_db_messages(user_db):
    user_db.add_message(role="user", content="hello")
    user_db.add_message(role="assistant", content="hi")
    msgs = user_db.get_recent_messages(10)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"

def test_user_db_jobs(user_db):
    job_id = user_db.add_job(cron="0 9 * * 1", description="standup reminder")
    jobs = user_db.list_active_jobs()
    assert len(jobs) == 1
    assert jobs[0]["id"] == job_id
    user_db.cancel_job(job_id)
    assert user_db.list_active_jobs() == []
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_db.py -v
```
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Create `bot/db.py`**

```python
import sqlite3
from datetime import datetime, timezone
from typing import Optional

class GlobalDB:
    def __init__(self, path: str):
        self.path = path
        self._init()

    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    username    TEXT,
                    status      TEXT DEFAULT 'pending',
                    is_admin    INTEGER DEFAULT 0,
                    created_at  TEXT
                )
            """)

    def get_user(self, telegram_id: int) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
            ).fetchone()
            return dict(row) if row else None

    def register_user(self, telegram_id: int, username: str):
        existing = self.get_user(telegram_id)
        if existing:
            return
        is_first = not self.list_users()
        status = "approved" if is_first else "pending"
        is_admin = 1 if is_first else 0
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO users (telegram_id, username, status, is_admin, created_at) VALUES (?,?,?,?,?)",
                (telegram_id, username, status, is_admin, datetime.now(timezone.utc).isoformat())
            )

    def approve_user(self, telegram_id: int):
        with self._conn() as conn:
            conn.execute("UPDATE users SET status='approved' WHERE telegram_id=?", (telegram_id,))

    def ban_user(self, telegram_id: int):
        with self._conn() as conn:
            conn.execute("UPDATE users SET status='banned' WHERE telegram_id=?", (telegram_id,))

    def delete_user(self, telegram_id: int):
        with self._conn() as conn:
            conn.execute("DELETE FROM users WHERE telegram_id=?", (telegram_id,))

    def list_users(self, status: str = None) -> list[dict]:
        with self._conn() as conn:
            if status:
                rows = conn.execute("SELECT * FROM users WHERE status=?", (status,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM users").fetchall()
            return [dict(r) for r in rows]

    def get_admin(self) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE is_admin=1").fetchone()
            return dict(row) if row else None


class UserDB:
    def __init__(self, path: str):
        self.path = path
        self._init()

    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    role      TEXT,
                    content   TEXT,
                    timestamp TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    cron        TEXT,
                    description TEXT,
                    next_run    TEXT,
                    active      INTEGER DEFAULT 1,
                    fail_count  INTEGER DEFAULT 0
                )
            """)

    def add_message(self, role: str, content: str):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO messages (role, content, timestamp) VALUES (?,?,?)",
                (role, content, datetime.now(timezone.utc).isoformat())
            )

    def get_recent_messages(self, n: int) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM messages ORDER BY id DESC LIMIT ?", (n,)
            ).fetchall()
            return [dict(r) for r in reversed(rows)]

    def add_job(self, cron: str, description: str) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO jobs (cron, description, active) VALUES (?,?,1)",
                (cron, description)
            )
            return cur.lastrowid

    def list_active_jobs(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM jobs WHERE active=1").fetchall()
            return [dict(r) for r in rows]

    def cancel_job(self, job_id: int):
        with self._conn() as conn:
            conn.execute("UPDATE jobs SET active=0 WHERE id=?", (job_id,))

    def increment_job_fail(self, job_id: int):
        with self._conn() as conn:
            conn.execute("UPDATE jobs SET fail_count = fail_count + 1 WHERE id=?", (job_id,))
            conn.execute("UPDATE jobs SET active=0 WHERE id=? AND fail_count >= 3", (job_id,))
```

**Step 4: Run tests**

```bash
pytest tests/test_db.py -v
```
Expected: all PASS

**Step 5: Commit**

```bash
git add bot/db.py tests/test_db.py
git commit -m "feat: database layer with GlobalDB and UserDB"
```

---

## Task 3: User Storage & Memory

**Files:**
- Create: `bot/storage.py`
- Create: `tests/test_storage.py`

**Step 1: Write failing tests**

```python
# tests/test_storage.py
import pytest
from bot.storage import UserStorage

@pytest.fixture
def storage(tmp_path):
    return UserStorage(data_dir=str(tmp_path), telegram_id=42)

def test_creates_user_dir(storage, tmp_path):
    assert (tmp_path / "users" / "42").exists()

def test_memory_empty_by_default(storage):
    assert storage.read_memory() == ""

def test_write_and_read_memory(storage):
    storage.write_memory("- Name: Alex\n- Timezone: UTC")
    assert "Alex" in storage.read_memory()

def test_user_db_accessible(storage):
    storage.db.add_message(role="user", content="hello")
    msgs = storage.db.get_recent_messages(5)
    assert len(msgs) == 1

def test_oauth_tokens_absent_by_default(storage):
    assert storage.load_oauth_tokens() is None

def test_save_and_load_oauth_tokens(storage):
    tokens = {"token": "abc", "refresh_token": "xyz", "expiry": "2030-01-01"}
    storage.save_oauth_tokens(tokens)
    loaded = storage.load_oauth_tokens()
    assert loaded["token"] == "abc"
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_storage.py -v
```

**Step 3: Create `bot/storage.py`**

```python
import json
import os
from bot.db import UserDB

class UserStorage:
    def __init__(self, data_dir: str, telegram_id: int):
        self.user_dir = os.path.join(data_dir, "users", str(telegram_id))
        os.makedirs(self.user_dir, exist_ok=True)
        self.db = UserDB(os.path.join(self.user_dir, "conversations.db"))
        self._memory_path = os.path.join(self.user_dir, "memory.md")
        self._tokens_path = os.path.join(self.user_dir, "oauth_tokens.json")

    def read_memory(self) -> str:
        if not os.path.exists(self._memory_path):
            return ""
        with open(self._memory_path) as f:
            return f.read()

    def write_memory(self, content: str):
        with open(self._memory_path, "w") as f:
            f.write(content)

    def load_oauth_tokens(self) -> dict | None:
        if not os.path.exists(self._tokens_path):
            return None
        with open(self._tokens_path) as f:
            return json.load(f)

    def save_oauth_tokens(self, tokens: dict):
        with open(self._tokens_path, "w") as f:
            json.dump(tokens, f)

    def delete(self):
        import shutil
        shutil.rmtree(self.user_dir, ignore_errors=True)
```

**Step 4: Run tests**

```bash
pytest tests/test_storage.py -v
```
Expected: all PASS

**Step 5: Commit**

```bash
git add bot/storage.py tests/test_storage.py
git commit -m "feat: per-user storage with memory and oauth token management"
```

---

## Task 4: Tool Registry (Stateless Tools)

**Files:**
- Create: `bot/tools/__init__.py`
- Create: `bot/tools/web_search.py`
- Create: `bot/tools/web_reader.py`
- Create: `bot/tools/wikipedia.py`
- Create: `bot/tools/youtube.py`
- Create: `bot/tools/arxiv.py`
- Create: `bot/tools/news.py`
- Create: `bot/tools/weather.py`
- Create: `bot/tools/currency.py`
- Create: `bot/tools/qrcode_tool.py`
- Create: `bot/tools/url_shortener.py`
- Create: `bot/tools/pdf_tool.py`
- Create: `bot/tools/registry.py`
- Create: `tests/test_tools.py`

**Step 1: Write failing tests (mocked — no real network calls in tests)**

```python
# tests/test_tools.py
import pytest
from unittest.mock import patch, MagicMock
from bot.tools.weather import get_weather
from bot.tools.currency import convert_currency
from bot.tools.qrcode_tool import generate_qr
from bot.tools.registry import build_tool_registry

def test_weather_returns_string():
    with patch("httpx.get") as mock_get:
        mock_get.return_value.json.return_value = {
            "current": {"temperature_2m": 15.0, "weathercode": 0}
        }
        mock_get.return_value.raise_for_status = MagicMock()
        result = get_weather("London")
        assert "15" in result or "London" in result

def test_currency_returns_string():
    with patch("httpx.get") as mock_get:
        mock_get.return_value.json.return_value = {"rates": {"USD": 1.08}}
        mock_get.return_value.raise_for_status = MagicMock()
        result = convert_currency(amount=100, from_currency="EUR", to_currency="USD")
        assert "USD" in result or "108" in result

def test_qr_returns_bytes():
    result = generate_qr("https://example.com")
    assert isinstance(result, bytes)
    assert len(result) > 0

def test_registry_returns_list():
    tools = build_tool_registry(user_storage=None, has_google=False)
    assert isinstance(tools, list)
    assert len(tools) > 5
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_tools.py -v
```

**Step 3: Create tool files**

`bot/tools/weather.py`:
```python
import httpx

def get_weather(location: str) -> str:
    try:
        geo = httpx.get(
            f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1"
        ).json()
        if not geo.get("results"):
            return f"Location '{location}' not found."
        r = geo["results"][0]
        lat, lon = r["latitude"], r["longitude"]
        data = httpx.get(
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,weathercode,windspeed_10m&timezone=auto"
        ).json()
        c = data["current"]
        return f"Weather in {location}: {c['temperature_2m']}°C, wind {c['windspeed_10m']} km/h"
    except Exception as e:
        return f"Weather unavailable: {e}"
```

`bot/tools/currency.py`:
```python
import httpx

def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    try:
        resp = httpx.get(f"https://api.frankfurter.app/latest?from={from_currency}&to={to_currency}").json()
        rate = resp["rates"][to_currency.upper()]
        result = round(amount * rate, 2)
        return f"{amount} {from_currency.upper()} = {result} {to_currency.upper()}"
    except Exception as e:
        return f"Currency conversion unavailable: {e}"
```

`bot/tools/qrcode_tool.py`:
```python
import io
import qrcode

def generate_qr(url: str) -> bytes:
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
```

`bot/tools/web_search.py`:
```python
from duckduckgo_search import DDGS

def web_search(query: str, max_results: int = 5) -> str:
    try:
        results = DDGS().text(query, max_results=max_results)
        if not results:
            return "No results found."
        return "\n\n".join(f"**{r['title']}**\n{r['href']}\n{r['body']}" for r in results)
    except Exception as e:
        return f"Web search unavailable: {e}"
```

`bot/tools/web_reader.py`:
```python
import httpx
from bs4 import BeautifulSoup

def read_webpage(url: str) -> str:
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return text[:8000]
    except Exception as e:
        return f"Could not read page: {e}"
```

`bot/tools/wikipedia.py`:
```python
import wikipedia as wiki

def search_wikipedia(query: str) -> str:
    try:
        page = wiki.page(wiki.search(query)[0])
        return page.summary[:3000]
    except Exception as e:
        return f"Wikipedia unavailable: {e}"
```

`bot/tools/youtube.py`:
```python
from youtube_transcript_api import YouTubeTranscriptApi
import re

def get_youtube_transcript(url: str) -> str:
    try:
        video_id = re.search(r"(?:v=|youtu\.be/)([^&\n?#]+)", url)
        if not video_id:
            return "Could not extract video ID from URL."
        transcript = YouTubeTranscriptApi.get_transcript(video_id.group(1))
        text = " ".join(t["text"] for t in transcript)
        return text[:6000]
    except Exception as e:
        return f"Transcript unavailable: {e}"
```

`bot/tools/arxiv.py`:
```python
import arxiv

def search_arxiv(query: str, max_results: int = 5) -> str:
    try:
        results = list(arxiv.Client().results(arxiv.Search(query=query, max_results=max_results)))
        if not results:
            return "No papers found."
        return "\n\n".join(f"**{r.title}**\n{r.entry_id}\n{r.summary[:300]}" for r in results)
    except Exception as e:
        return f"arXiv search unavailable: {e}"
```

`bot/tools/news.py`:
```python
import feedparser

FEEDS = [
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
]

def get_news(topic: str = "") -> str:
    try:
        items = []
        for feed_url in FEEDS:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:5]:
                if not topic or topic.lower() in entry.title.lower():
                    items.append(f"**{entry.title}**\n{entry.link}")
        return "\n\n".join(items[:10]) if items else "No news found."
    except Exception as e:
        return f"News unavailable: {e}"
```

`bot/tools/url_shortener.py`:
```python
import httpx

def shorten_url(url: str) -> str:
    try:
        resp = httpx.get(f"https://tinyurl.com/api-create.php?url={url}", timeout=10)
        return resp.text.strip()
    except Exception as e:
        return f"URL shortener unavailable: {e}"
```

`bot/tools/pdf_tool.py`:
```python
from pypdf import PdfReader
import io

def extract_pdf_text(file_bytes: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return text[:8000]
    except Exception as e:
        return f"Could not read PDF: {e}"
```

`bot/tools/registry.py`:
```python
from bot.tools.web_search import web_search
from bot.tools.web_reader import read_webpage
from bot.tools.wikipedia import search_wikipedia
from bot.tools.youtube import get_youtube_transcript
from bot.tools.arxiv import search_arxiv
from bot.tools.news import get_news
from bot.tools.weather import get_weather
from bot.tools.currency import convert_currency
from bot.tools.url_shortener import shorten_url

def build_tool_registry(user_storage, has_google: bool) -> list:
    tools = [
        web_search, read_webpage, search_wikipedia,
        get_youtube_transcript, search_arxiv, get_news,
        get_weather, convert_currency, shorten_url,
    ]
    if has_google:
        from bot.tools.google_calendar import (
            list_calendar_events, create_calendar_event
        )
        from bot.tools.gmail import list_emails, send_email
        from bot.tools.google_drive import search_drive_files
        tools += [list_calendar_events, create_calendar_event,
                  list_emails, send_email, search_drive_files]
    return tools
```

**Step 4: Run tests**

```bash
pytest tests/test_tools.py -v
```
Expected: all PASS

**Step 5: Commit**

```bash
git add bot/tools/ tests/test_tools.py
git commit -m "feat: stateless tool implementations and registry"
```

---

## Task 5: Memory Tool & Agent Runner

**Files:**
- Create: `bot/tools/memory_tool.py`
- Create: `bot/agent.py`
- Create: `tests/test_agent.py`

**Step 1: Write failing tests**

```python
# tests/test_agent.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from bot.storage import UserStorage
from bot.agent import build_system_prompt, AgentRunner

@pytest.fixture
def storage(tmp_path):
    s = UserStorage(data_dir=str(tmp_path), telegram_id=1)
    s.write_memory("- Name: Alice\n- Timezone: UTC")
    return s

def test_system_prompt_includes_memory(storage):
    prompt = build_system_prompt(storage)
    assert "Alice" in prompt

def test_system_prompt_includes_date(storage):
    prompt = build_system_prompt(storage)
    assert "2026" in prompt or "date" in prompt.lower()

@pytest.mark.asyncio
async def test_agent_runner_returns_text(storage):
    runner = AgentRunner(anthropic_api_key="test", storage=storage, tools=[])
    with patch("anthropic.Anthropic") as mock_client:
        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Hello!")]
        mock_client.return_value.beta.messages.create.return_value = mock_response
        result = await runner.run("hi")
    assert isinstance(result, str)
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_agent.py -v
```

**Step 3: Create `bot/tools/memory_tool.py`**

```python
def update_memory(new_content: str, storage) -> str:
    """Update the persistent memory file with new information about the user."""
    storage.write_memory(new_content)
    return "Memory updated."
```

**Step 4: Create `bot/agent.py`**

```python
import asyncio
from datetime import datetime, timezone
from functools import partial
import anthropic
from bot.storage import UserStorage

SYSTEM_TEMPLATE = """You are a helpful personal AI assistant on Telegram.

Today's date and time: {datetime}

What you know about this user:
{memory}

Be concise. Use bullet points when listing things. Respond in the same language the user writes in.

You have access to tools — use them when they help answer the user's request.
To remember something important about the user long-term, call the update_memory tool with the complete updated memory content.
"""

def build_system_prompt(storage: UserStorage) -> str:
    memory = storage.read_memory() or "Nothing known yet."
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return SYSTEM_TEMPLATE.format(datetime=now, memory=memory)


class AgentRunner:
    def __init__(self, anthropic_api_key: str, storage: UserStorage, tools: list):
        self.client = anthropic.Anthropic(api_key=anthropic_api_key)
        self.storage = storage
        self.tools = tools
        self._tool_map = {fn.__name__: fn for fn in tools}

    async def run(self, user_message: str) -> str:
        history = self.storage.db.get_recent_messages(20)
        messages = [{"role": m["role"], "content": m["content"]} for m in history]
        messages.append({"role": "user", "content": user_message})

        system = build_system_prompt(self.storage)
        anthropic_tools = self._build_anthropic_tools()

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            partial(
                self.client.messages.create,
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=system,
                messages=messages,
                tools=anthropic_tools if anthropic_tools else anthropic.NOT_GIVEN,
            )
        )

        while response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = self._call_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                    })
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
            response = await loop.run_in_executor(
                None,
                partial(
                    self.client.messages.create,
                    model="claude-sonnet-4-6",
                    max_tokens=4096,
                    system=system,
                    messages=messages,
                    tools=anthropic_tools,
                )
            )

        text = next((b.text for b in response.content if hasattr(b, "text")), "")
        return text

    def _call_tool(self, name: str, inputs: dict) -> str:
        fn = self._tool_map.get(name)
        if not fn:
            return f"Unknown tool: {name}"
        if name == "update_memory":
            inputs["storage"] = self.storage
        try:
            return fn(**inputs)
        except Exception as e:
            return f"Tool error: {e}"

    def _build_anthropic_tools(self) -> list:
        import inspect
        tools = []
        for fn in self.tools:
            sig = inspect.signature(fn)
            props = {}
            required = []
            for pname, param in sig.parameters.items():
                if pname == "storage":
                    continue
                props[pname] = {"type": "string", "description": pname}
                if param.default is inspect.Parameter.empty:
                    required.append(pname)
            tools.append({
                "name": fn.__name__,
                "description": fn.__doc__ or fn.__name__,
                "input_schema": {
                    "type": "object",
                    "properties": props,
                    "required": required,
                }
            })
        return tools
```

**Step 5: Run tests**

```bash
pytest tests/test_agent.py -v
```
Expected: all PASS

**Step 6: Commit**

```bash
git add bot/agent.py bot/tools/memory_tool.py tests/test_agent.py
git commit -m "feat: agent runner with tool loop and memory tool"
```

---

## Task 6: Telegram Handler & Auth

**Files:**
- Create: `bot/handler.py`
- Create: `bot/main.py`
- Create: `tests/test_handler.py`

**Step 1: Write failing tests**

```python
# tests/test_handler.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bot.db import GlobalDB

@pytest.fixture
def global_db(tmp_path):
    return GlobalDB(str(tmp_path / "global.db"))

def test_first_start_creates_admin(global_db):
    global_db.register_user(telegram_id=100, username="admin")
    user = global_db.get_user(100)
    assert user["is_admin"] == 1
    assert user["status"] == "approved"

def test_second_user_is_pending(global_db):
    global_db.register_user(telegram_id=100, username="admin")
    global_db.register_user(telegram_id=200, username="user2")
    assert global_db.get_user(200)["status"] == "pending"

def test_banned_user_blocked(global_db):
    global_db.register_user(telegram_id=100, username="admin")
    global_db.register_user(telegram_id=200, username="user2")
    global_db.ban_user(200)
    assert global_db.get_user(200)["status"] == "banned"
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_handler.py -v
```

**Step 3: Create `bot/handler.py`**

```python
import asyncio
import logging
import os
from telegram import Update
from telegram.ext import ContextTypes
from bot.db import GlobalDB
from bot.storage import UserStorage
from bot.agent import AgentRunner
from bot.tools.registry import build_tool_registry
from bot.tools.memory_tool import update_memory
from functools import partial

logger = logging.getLogger(__name__)

HELP_TEXT = """I'm your personal AI assistant!

📅 *Productivity*
• Google Calendar, Gmail, Drive (type /connect google)
• Reminders — "remind me every Monday at 9am to..."

🔍 *Research*
• Web search & page summaries
• Wikipedia, arXiv, YouTube transcripts
• News digest

🌤 *Utilities*
• Weather, currency conversion
• QR codes, URL shortener
• PDF summaries — send any PDF

🎙 *Voice*
• Send a voice note — I'll transcribe and respond

Just talk to me naturally — no need for commands!

Commands: /help /connect /status"""


class BotHandler:
    def __init__(self, config, global_db: GlobalDB):
        self.config = config
        self.global_db = global_db

    def _get_storage(self, telegram_id: int) -> UserStorage:
        return UserStorage(data_dir=self.config.data_dir, telegram_id=telegram_id)

    def _get_runner(self, storage: UserStorage) -> AgentRunner:
        has_google = storage.load_oauth_tokens() is not None
        tools = build_tool_registry(storage, has_google=has_google)
        tools.append(partial(update_memory, storage=storage))
        tools[-1].__name__ = "update_memory"
        tools[-1].__doc__ = "Update long-term memory about this user. Pass the complete updated memory content."
        return AgentRunner(
            anthropic_api_key=self.config.anthropic_api_key,
            storage=storage,
            tools=tools,
        )

    async def start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        username = update.effective_user.username or ""
        self.global_db.register_user(telegram_id=uid, username=username)
        user = self.global_db.get_user(uid)

        if user["is_admin"]:
            await update.message.reply_text(
                "Welcome! You're the admin. The bot is ready.\n\n"
                "Use /help to see what I can do, or /admin to manage users."
            )
        else:
            admin = self.global_db.get_admin()
            if admin:
                await ctx.bot.send_message(
                    chat_id=admin["telegram_id"],
                    text=f"New user request: @{username} (id: {uid})\n"
                         f"Approve: /approve {uid}  |  Ban: /ban {uid}"
                )
            await update.message.reply_text(
                "Hi! Access is by approval only. Your request has been sent to the admin."
            )

    async def help_command(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        user = self.global_db.get_user(uid)
        if not user or user["status"] != "approved":
            return
        await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")

    async def approve_command(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        user = self.global_db.get_user(uid)
        if not user or not user["is_admin"]:
            return
        if not ctx.args:
            await update.message.reply_text("Usage: /approve <telegram_id>")
            return
        target_id = int(ctx.args[0])
        self.global_db.approve_user(target_id)
        target = self.global_db.get_user(target_id)
        await update.message.reply_text(f"User {target_id} approved.")
        try:
            await ctx.bot.send_message(
                chat_id=target_id,
                text="You're approved! I'm your personal AI assistant. Type /help to see what I can do."
            )
        except Exception:
            pass

    async def ban_command(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        user = self.global_db.get_user(uid)
        if not user or not user["is_admin"]:
            return
        if not ctx.args:
            await update.message.reply_text("Usage: /ban <telegram_id>")
            return
        self.global_db.ban_user(int(ctx.args[0]))
        await update.message.reply_text(f"User {ctx.args[0]} banned.")

    async def message(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        user = self.global_db.get_user(uid)
        if not user or user["status"] != "approved":
            return

        text = update.message.text or ""
        storage = self._get_storage(uid)
        storage.db.add_message(role="user", content=text)

        await ctx.bot.send_chat_action(chat_id=uid, action="typing")
        runner = self._get_runner(storage)
        try:
            reply = await runner.run(text)
        except Exception as e:
            logger.exception("Agent error")
            reply = "Something went wrong, please try again."
            admin = self.global_db.get_admin()
            if admin:
                try:
                    await ctx.bot.send_message(
                        chat_id=admin["telegram_id"],
                        text=f"Error for user {uid}: {e}"
                    )
                except Exception:
                    pass

        storage.db.add_message(role="assistant", content=reply)
        await update.message.reply_text(reply)

    async def voice(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        user = self.global_db.get_user(uid)
        if not user or user["status"] != "approved":
            return

        await update.message.reply_text("Got it, transcribing your voice message...")
        voice_file = await update.message.voice.get_file()
        ogg_bytes = await voice_file.download_as_bytearray()

        loop = asyncio.get_event_loop()
        transcript = await loop.run_in_executor(None, self._transcribe, bytes(ogg_bytes))

        storage = self._get_storage(uid)
        storage.db.add_message(role="user", content=f"[Voice message] {transcript}")
        runner = self._get_runner(storage)
        reply = await runner.run(transcript)
        storage.db.add_message(role="assistant", content=reply)
        await update.message.reply_text(reply)

    def _transcribe(self, ogg_bytes: bytes) -> str:
        import tempfile
        from faster_whisper import WhisperModel
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            f.write(ogg_bytes)
            path = f.name
        segments, _ = model.transcribe(path)
        os.unlink(path)
        return " ".join(s.text for s in segments)
```

**Step 4: Create `bot/main.py`**

```python
import logging
import os
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from bot.config import Config
from bot.db import GlobalDB
from bot.handler import BotHandler

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    handlers=[
        logging.FileHandler("/data/logs/bot.log"),
        logging.StreamHandler(),
    ]
)

def main():
    os.makedirs("/data/logs", exist_ok=True)
    config = Config()
    global_db = GlobalDB(os.path.join(config.data_dir, "global.db"))
    handler = BotHandler(config=config, global_db=global_db)

    app = Application.builder().token(config.telegram_token).build()
    app.add_handler(CommandHandler("start", handler.start))
    app.add_handler(CommandHandler("help", handler.help_command))
    app.add_handler(CommandHandler("approve", handler.approve_command))
    app.add_handler(CommandHandler("ban", handler.ban_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler.message))
    app.add_handler(MessageHandler(filters.VOICE, handler.voice))

    app.run_polling()

if __name__ == "__main__":
    main()
```

**Step 5: Run tests**

```bash
pytest tests/test_handler.py -v
```
Expected: all PASS

**Step 6: Commit**

```bash
git add bot/handler.py bot/main.py tests/test_handler.py
git commit -m "feat: telegram handler with auth gating, commands, voice support"
```

---

## Task 7: Google OAuth Flow

**Files:**
- Create: `bot/oauth.py`
- Create: `bot/tools/google_calendar.py`
- Create: `bot/tools/gmail.py`
- Create: `bot/tools/google_drive.py`
- Create: `tests/test_oauth.py`

**Step 1: Write failing tests**

```python
# tests/test_oauth.py
import pytest
from unittest.mock import patch, MagicMock
from bot.oauth import OAuthManager, extract_auth_code_from_url

def test_extract_code_from_url():
    url = "https://accounts.google.com/o/oauth2/approval?code=4/abc123&scope=..."
    code = extract_auth_code_from_url(url)
    assert code == "4/abc123"

def test_extract_code_returns_none_for_invalid():
    assert extract_auth_code_from_url("https://example.com/no-code") is None

def test_oauth_manager_builds_auth_url():
    manager = OAuthManager(client_id="cid", client_secret="csecret")
    url = manager.get_auth_url()
    assert "accounts.google.com" in url
    assert "cid" in url
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_oauth.py -v
```

**Step 3: Create `bot/oauth.py`**

```python
import re
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import json

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/drive.readonly",
]

REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"


def extract_auth_code_from_url(url: str) -> str | None:
    match = re.search(r"[?&]code=([^&\s]+)", url)
    return match.group(1) if match else None


class OAuthManager:
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret

    def _make_flow(self) -> Flow:
        return Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI,
        )

    def get_auth_url(self) -> str:
        flow = self._make_flow()
        auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")
        return auth_url

    def exchange_code(self, code: str) -> dict:
        flow = self._make_flow()
        flow.fetch_token(code=code)
        creds = flow.credentials
        return {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes or []),
        }

    def get_credentials(self, tokens: dict) -> Credentials:
        creds = Credentials(
            token=tokens["token"],
            refresh_token=tokens["refresh_token"],
            token_uri=tokens.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=tokens.get("client_id", self.client_id),
            client_secret=tokens.get("client_secret", self.client_secret),
            scopes=tokens.get("scopes", SCOPES),
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return creds
```

**Step 4: Create Google tool stubs**

`bot/tools/google_calendar.py`:
```python
from googleapiclient.discovery import build

def list_calendar_events(time_min: str = None, max_results: int = 10, storage=None) -> str:
    """List upcoming calendar events. time_min in ISO format e.g. '2026-03-01T00:00:00Z'"""
    try:
        from bot.oauth import OAuthManager
        tokens = storage.load_oauth_tokens()
        if not tokens:
            return "Google not connected. Use /connect google."
        from bot.config import Config
        config = Config()
        creds = OAuthManager(config.google_client_id, config.google_client_secret).get_credentials(tokens)
        service = build("calendar", "v3", credentials=creds)
        from datetime import datetime, timezone
        tmin = time_min or datetime.now(timezone.utc).isoformat()
        events = service.events().list(
            calendarId="primary", timeMin=tmin,
            maxResults=max_results, singleEvents=True, orderBy="startTime"
        ).execute().get("items", [])
        if not events:
            return "No upcoming events."
        return "\n".join(
            f"• {e['summary']} — {e['start'].get('dateTime', e['start'].get('date'))}"
            for e in events
        )
    except Exception as e:
        return f"Calendar unavailable: {e}"


def create_calendar_event(title: str, start: str, end: str, description: str = "", storage=None) -> str:
    """Create a calendar event. start/end in ISO format."""
    try:
        from bot.oauth import OAuthManager
        from bot.config import Config
        tokens = storage.load_oauth_tokens()
        if not tokens:
            return "Google not connected."
        config = Config()
        creds = OAuthManager(config.google_client_id, config.google_client_secret).get_credentials(tokens)
        service = build("calendar", "v3", credentials=creds)
        event = service.events().insert(calendarId="primary", body={
            "summary": title, "description": description,
            "start": {"dateTime": start}, "end": {"dateTime": end}
        }).execute()
        return f"Event created: {event.get('htmlLink')}"
    except Exception as e:
        return f"Could not create event: {e}"
```

`bot/tools/gmail.py`:
```python
from googleapiclient.discovery import build
import base64, email

def list_emails(max_results: int = 10, query: str = "", storage=None) -> str:
    """List recent emails. query supports Gmail search syntax."""
    try:
        from bot.oauth import OAuthManager
        from bot.config import Config
        tokens = storage.load_oauth_tokens()
        if not tokens:
            return "Google not connected."
        config = Config()
        creds = OAuthManager(config.google_client_id, config.google_client_secret).get_credentials(tokens)
        service = build("gmail", "v1", credentials=creds)
        msgs = service.users().messages().list(
            userId="me", q=query, maxResults=max_results
        ).execute().get("messages", [])
        result = []
        for m in msgs[:5]:
            detail = service.users().messages().get(userId="me", id=m["id"], format="metadata",
                metadataHeaders=["Subject","From"]).execute()
            headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
            result.append(f"• {headers.get('Subject','(no subject)')} — from {headers.get('From','')}")
        return "\n".join(result) if result else "No emails found."
    except Exception as e:
        return f"Gmail unavailable: {e}"


def send_email(to: str, subject: str, body: str, storage=None) -> str:
    """Send an email."""
    try:
        from bot.oauth import OAuthManager
        from bot.config import Config
        tokens = storage.load_oauth_tokens()
        if not tokens:
            return "Google not connected."
        config = Config()
        creds = OAuthManager(config.google_client_id, config.google_client_secret).get_credentials(tokens)
        service = build("gmail", "v1", credentials=creds)
        msg = email.message.EmailMessage()
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return f"Email sent to {to}."
    except Exception as e:
        return f"Could not send email: {e}"
```

`bot/tools/google_drive.py`:
```python
from googleapiclient.discovery import build

def search_drive_files(query: str, max_results: int = 10, storage=None) -> str:
    """Search Google Drive files by name or content."""
    try:
        from bot.oauth import OAuthManager
        from bot.config import Config
        tokens = storage.load_oauth_tokens()
        if not tokens:
            return "Google not connected."
        config = Config()
        creds = OAuthManager(config.google_client_id, config.google_client_secret).get_credentials(tokens)
        service = build("drive", "v3", credentials=creds)
        files = service.files().list(
            q=f"name contains '{query}'",
            pageSize=max_results,
            fields="files(id, name, mimeType, webViewLink)"
        ).execute().get("files", [])
        if not files:
            return "No files found."
        return "\n".join(f"• {f['name']} — {f.get('webViewLink','')}" for f in files)
    except Exception as e:
        return f"Drive unavailable: {e}"
```

**Step 5: Run tests**

```bash
pytest tests/test_oauth.py -v
```
Expected: all PASS

**Step 6: Add `/connect google` handler to `bot/handler.py`**

Add to `BotHandler`:

```python
async def connect_command(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = self.global_db.get_user(uid)
    if not user or user["status"] != "approved":
        return
    if not self.config.google_client_id:
        await update.message.reply_text("Google integration is not configured by the admin.")
        return
    from bot.oauth import OAuthManager
    manager = OAuthManager(self.config.google_client_id, self.config.google_client_secret)
    url = manager.get_auth_url()
    await update.message.reply_text(
        f"Click to authorize Google:\n{url}\n\n"
        "After authorizing, copy the full URL from your browser (even if it shows an error) and paste it here."
    )
    ctx.user_data["awaiting_oauth"] = True

async def message(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # Add at top of existing message handler:
    if ctx.user_data.get("awaiting_oauth"):
        ctx.user_data.pop("awaiting_oauth")
        url = update.message.text
        from bot.oauth import OAuthManager, extract_auth_code_from_url
        code = extract_auth_code_from_url(url)
        if not code:
            await update.message.reply_text("Could not find auth code in that URL. Try /connect google again.")
            return
        manager = OAuthManager(self.config.google_client_id, self.config.google_client_secret)
        tokens = manager.exchange_code(code)
        storage = self._get_storage(update.effective_user.id)
        storage.save_oauth_tokens(tokens)
        await update.message.reply_text("Google connected! Calendar, Gmail and Drive are now available.")
        return
    # ... rest of existing message handler
```

**Step 7: Commit**

```bash
git add bot/oauth.py bot/tools/google_calendar.py bot/tools/gmail.py bot/tools/google_drive.py tests/test_oauth.py
git commit -m "feat: Google OAuth flow and Calendar/Gmail/Drive tools"
```

---

## Task 8: Scheduler (Reminders)

**Files:**
- Create: `bot/scheduler.py`
- Create: `tests/test_scheduler.py`

**Step 1: Write failing tests**

```python
# tests/test_scheduler.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bot.scheduler import parse_reminder_request

def test_parse_returns_cron_and_description():
    result = parse_reminder_request("every Monday at 9am standup")
    assert result is not None
    assert "cron" in result
    assert "description" in result

def test_parse_daily_reminder():
    result = parse_reminder_request("every day at 8am take pills")
    assert result is not None
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_scheduler.py -v
```

**Step 3: Create `bot/scheduler.py`**

```python
import re
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

DAY_MAP = {
    "monday": "mon", "tuesday": "tue", "wednesday": "wed",
    "thursday": "thu", "friday": "fri", "saturday": "sat", "sunday": "sun"
}


def parse_reminder_request(text: str) -> dict | None:
    text_lower = text.lower()
    hour = 9
    minute = 0
    time_match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text_lower)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or 0)
        if time_match.group(3) == "pm" and hour < 12:
            hour += 12
        if time_match.group(3) == "am" and hour == 12:
            hour = 0

    day_of_week = "*"
    for day, abbr in DAY_MAP.items():
        if day in text_lower:
            day_of_week = abbr
            break

    cron = f"{minute} {hour} * * {day_of_week}"
    description = re.sub(r"remind(?:\s+me)?|every\s+\w+|at\s+\d+(?::\d+)?\s*(?:am|pm)?", "", text, flags=re.I).strip()
    return {"cron": cron, "description": description or text}


class ReminderScheduler:
    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()

    def start(self):
        self.scheduler.start()

    def add_job(self, telegram_id: int, job_id: int, cron: str, description: str):
        parts = cron.split()
        trigger = CronTrigger(minute=parts[0], hour=parts[1], day=parts[2],
                              month=parts[3], day_of_week=parts[4])
        self.scheduler.add_job(
            self._send_reminder,
            trigger=trigger,
            args=[telegram_id, job_id, description],
            id=f"job_{job_id}",
            replace_existing=True,
        )

    def remove_job(self, job_id: int):
        try:
            self.scheduler.remove_job(f"job_{job_id}")
        except Exception:
            pass

    async def _send_reminder(self, telegram_id: int, job_id: int, description: str):
        try:
            await self.bot.send_message(chat_id=telegram_id, text=f"Reminder: {description}")
        except Exception as e:
            logger.error(f"Reminder delivery failed for job {job_id}: {e}")
```

**Step 4: Run tests**

```bash
pytest tests/test_scheduler.py -v
```
Expected: all PASS

**Step 5: Commit**

```bash
git add bot/scheduler.py tests/test_scheduler.py
git commit -m "feat: reminder scheduler with cron parsing"
```

---

## Task 9: Setup Script & Install Script

**Files:**
- Create: `setup.py`
- Create: `install.sh`

**Step 1: Create `setup.py`**

```python
#!/usr/bin/env python3
"""Interactive setup script — run once after cloning."""
import os, json, time, subprocess, sys

def check(label, fn):
    try:
        result = fn()
        print(f"  ✓ {label}" + (f": {result}" if result else ""))
        return True
    except Exception as e:
        print(f"  ✗ {label}: {e}")
        return False

def validate_telegram_token(token):
    import urllib.request
    url = f"https://api.telegram.org/bot{token}/getMe"
    with urllib.request.urlopen(url, timeout=5) as r:
        data = json.loads(r.read())
    assert data["ok"], "Invalid token"
    return "@" + data["result"]["username"]

def validate_anthropic_key(key):
    import urllib.request, urllib.error
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/models",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01"}
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return "valid"
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise ValueError("Invalid API key")
        return "valid"

def get_admin_telegram_id(token):
    import urllib.request
    print("\n  Send any message to your bot on Telegram, then press Enter...")
    input("  Press Enter when done: ")
    url = f"https://api.telegram.org/bot{token}/getUpdates?limit=1&offset=-1"
    with urllib.request.urlopen(url, timeout=5) as r:
        data = json.loads(r.read())
    updates = data.get("result", [])
    if not updates:
        raise ValueError("No messages received yet")
    return updates[-1]["message"]["from"]["id"]

def write_env(values):
    with open(".env", "w") as f:
        for k, v in values.items():
            if v:
                f.write(f"{k}={v}\n")
    print("\n  ✓ .env written")

def main():
    print("\n=== Bot Setup ===\n")
    env = {}

    print("Step 1: Telegram Bot Token")
    while True:
        token = input("  Paste your token from @BotFather: ").strip()
        if check("Validating token", lambda: validate_telegram_token(token)):
            env["TELEGRAM_TOKEN"] = token
            break

    print("\nStep 2: Anthropic API Key")
    while True:
        key = input("  Paste your Anthropic API key: ").strip()
        if check("Validating key", lambda: validate_anthropic_key(key)):
            env["ANTHROPIC_API_KEY"] = key
            break

    print("\nStep 3: Google Integration (optional)")
    want_google = input("  Enable Gmail, Calendar and Drive? [y/n]: ").strip().lower() == "y"
    if want_google:
        env["GOOGLE_CLIENT_ID"] = input("  Google Client ID: ").strip()
        env["GOOGLE_CLIENT_SECRET"] = input("  Google Client Secret: ").strip()

    write_env(env)

    print("\nStep 4: Detecting your Telegram user ID for admin access")
    print("  Starting bot temporarily...")
    subprocess.Popen(["docker", "compose", "up", "-d", "--build"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(5)
    try:
        admin_id = get_admin_telegram_id(token)
        print(f"  ✓ Admin ID detected: {admin_id}")
    except Exception as e:
        print(f"  Could not auto-detect: {e}")
        admin_id = input("  Enter your Telegram user ID manually: ").strip()

    print("\nSetup complete!")
    print(f"\nStart the bot: docker compose up -d")
    print(f"Admin CLI:     docker compose exec bot python admin.py")

if __name__ == "__main__":
    main()
```

**Step 2: Create `install.sh`**

```bash
#!/usr/bin/env bash
set -e

REPO="https://github.com/<owner>/<repo>.git"
INSTALL_DIR="$HOME/mybot"

echo ""
echo "=== Bot Installer ==="
echo ""

# Check dependencies
for cmd in docker git python3; do
  if ! command -v $cmd &>/dev/null; then
    echo "Error: $cmd is required but not installed."
    exit 1
  fi
done

if ! docker compose version &>/dev/null; then
  echo "Error: docker compose plugin is required."
  exit 1
fi

# Clone
if [ -d "$INSTALL_DIR" ]; then
  echo "Directory $INSTALL_DIR already exists. Updating..."
  git -C "$INSTALL_DIR" pull
else
  git clone "$REPO" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# Install Python deps for setup script
pip3 install python-dotenv --quiet

# Run interactive setup
python3 setup.py

# Add alias
ALIAS_LINE="alias botadmin='docker compose -f $INSTALL_DIR/docker-compose.yml exec bot python admin.py'"
if ! grep -q "botadmin" ~/.bashrc 2>/dev/null; then
  echo "$ALIAS_LINE" >> ~/.bashrc
fi
if ! grep -q "botadmin" ~/.zshrc 2>/dev/null; then
  echo "$ALIAS_LINE" >> ~/.zshrc 2>/dev/null || true
fi

echo ""
echo "Done! Run 'botadmin' to manage your bot (reload shell first or run: source ~/.bashrc)"
```

**Step 3: Make executable and commit**

```bash
chmod +x install.sh
git add setup.py install.sh
git commit -m "feat: interactive setup script and one-liner installer"
```

---

## Task 10: Admin CLI

**Files:**
- Create: `admin.py`

**Step 1: Create `admin.py`**

```python
#!/usr/bin/env python3
"""Admin CLI — run via: docker compose exec bot python admin.py"""
import os, sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
DATA_DIR = os.getenv("DATA_DIR", "/data")

from bot.db import GlobalDB

global_db = GlobalDB(os.path.join(DATA_DIR, "global.db"))


def clear():
    os.system("clear")

def pause():
    input("\nPress Enter to continue...")

def pick_user(prompt="Select user") -> dict | None:
    users = global_db.list_users()
    if not users:
        print("No users found.")
        return None
    print(f"\n{prompt}:")
    for i, u in enumerate(users, 1):
        print(f"  [{i}] @{u['username'] or '?'} ({u['telegram_id']}) — {u['status']}")
    print("  [t] Type user ID directly")
    choice = input("> ").strip()
    if choice == "t":
        uid = int(input("User ID: ").strip())
        return global_db.get_user(uid)
    try:
        return users[int(choice) - 1]
    except (ValueError, IndexError):
        print("Invalid choice.")
        return None


def menu_stats():
    clear()
    print("=== Status & Stats ===\n")
    users = global_db.list_users()
    approved = sum(1 for u in users if u["status"] == "approved")
    pending  = sum(1 for u in users if u["status"] == "pending")
    banned   = sum(1 for u in users if u["status"] == "banned")
    print(f"Total users:   {len(users)}")
    print(f"  Approved:    {approved}")
    print(f"  Pending:     {pending}")
    print(f"  Banned:      {banned}")
    pause()


def menu_users():
    while True:
        clear()
        print("=== Users ===\n")
        print("1. List all users")
        print("2. List pending approvals")
        print("3. Approve user")
        print("4. Ban user")
        print("5. Delete user + data")
        print("6. View user memory")
        print("0. Back")
        choice = input("> ").strip()

        if choice == "1":
            users = global_db.list_users()
            for u in users:
                print(f"  @{u['username'] or '?'} ({u['telegram_id']}) — {u['status']}" +
                      (" [admin]" if u["is_admin"] else ""))
            pause()

        elif choice == "2":
            pending = global_db.list_users(status="pending")
            if not pending:
                print("No pending approvals.")
                pause()
                continue
            for u in pending:
                print(f"  @{u['username'] or '?'} ({u['telegram_id']}) — {u['created_at']}")
                action = input("  [a]pprove / [b]an / [s]kip: ").strip().lower()
                if action == "a":
                    global_db.approve_user(u["telegram_id"])
                    print("  Approved.")
                elif action == "b":
                    global_db.ban_user(u["telegram_id"])
                    print("  Banned.")
            pause()

        elif choice == "3":
            u = pick_user("Approve which user")
            if u:
                global_db.approve_user(u["telegram_id"])
                print(f"Approved {u['telegram_id']}.")
                pause()

        elif choice == "4":
            u = pick_user("Ban which user")
            if u:
                global_db.ban_user(u["telegram_id"])
                print(f"Banned {u['telegram_id']}.")
                pause()

        elif choice == "5":
            u = pick_user("Delete which user")
            if u:
                confirm = input(f"Delete @{u['username']} and all their data? [yes/no]: ")
                if confirm == "yes":
                    from bot.storage import UserStorage
                    UserStorage(DATA_DIR, u["telegram_id"]).delete()
                    global_db.delete_user(u["telegram_id"])
                    print("Deleted.")
                pause()

        elif choice == "6":
            u = pick_user("View memory for")
            if u:
                from bot.storage import UserStorage
                memory = UserStorage(DATA_DIR, u["telegram_id"]).read_memory()
                print(f"\n--- memory.md for @{u['username']} ---\n{memory or '(empty)'}\n---")
                pause()

        elif choice == "0":
            break


def menu_logs():
    while True:
        clear()
        print("=== Logs ===\n")
        print("1. View recent logs (last 50 lines)")
        print("2. View errors only")
        print("3. Search logs by user")
        print("4. Clear old logs")
        print("0. Back")
        choice = input("> ").strip()

        if choice == "1":
            path = os.path.join(DATA_DIR, "logs", "bot.log")
            if os.path.exists(path):
                lines = open(path).readlines()
                print("".join(lines[-50:]))
            else:
                print("No log file yet.")
            pause()

        elif choice == "2":
            path = os.path.join(DATA_DIR, "logs", "errors.log")
            if os.path.exists(path):
                print(open(path).read())
            else:
                print("No error log yet.")
            pause()

        elif choice == "3":
            u = pick_user("Search logs for")
            if u:
                uid = str(u["telegram_id"])
                path = os.path.join(DATA_DIR, "logs", "bot.log")
                if os.path.exists(path):
                    matches = [l for l in open(path) if uid in l]
                    print(f"\nLog entries for {uid}:\n" + "".join(matches[-30:]) if matches else "No entries found.")
                pause()

        elif choice == "4":
            confirm = input("Clear all logs? [yes/no]: ")
            if confirm == "yes":
                for f in ["bot.log", "errors.log"]:
                    p = os.path.join(DATA_DIR, "logs", f)
                    if os.path.exists(p):
                        open(p, "w").close()
                print("Logs cleared.")
            pause()

        elif choice == "0":
            break


def main():
    while True:
        clear()
        print("=== Bot Admin ===\n")
        print("1. Status & Stats")
        print("2. Users")
        print("3. Logs")
        print("0. Exit")
        choice = input("> ").strip()
        if choice == "1":
            menu_stats()
        elif choice == "2":
            menu_users()
        elif choice == "3":
            menu_logs()
        elif choice == "0":
            sys.exit(0)


if __name__ == "__main__":
    main()
```

**Step 2: Commit**

```bash
git add admin.py
git commit -m "feat: CLI admin tool with user management and log search"
```

---

## Task 11: PDF & QR Code Handlers in Telegram

**Files:**
- Modify: `bot/handler.py`

**Step 1: Add document and photo handlers to `BotHandler`**

Add to `bot/handler.py`:

```python
async def document(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = self.global_db.get_user(uid)
    if not user or user["status"] != "approved":
        return
    doc = update.message.document
    if not doc.mime_type == "application/pdf":
        await update.message.reply_text("Send me a PDF and I'll summarize it.")
        return
    await update.message.reply_text("Reading your PDF, I'll send the summary shortly...")
    file = await doc.get_file()
    pdf_bytes = await file.download_as_bytearray()

    async def process():
        from bot.tools.pdf_tool import extract_pdf_text
        text = extract_pdf_text(bytes(pdf_bytes))
        storage = self._get_storage(uid)
        runner = self._get_runner(storage)
        reply = await runner.run(f"Summarize this document:\n\n{text}")
        await ctx.bot.send_message(chat_id=uid, text=reply)

    asyncio.create_task(process())
```

And register in `main.py`:
```python
app.add_handler(MessageHandler(filters.Document.PDF, handler.document))
```

**Step 2: Commit**

```bash
git add bot/handler.py bot/main.py
git commit -m "feat: async PDF handler with background processing"
```

---

## Task 12: Logging & Error Notification

**Files:**
- Create: `bot/logger.py`
- Modify: `bot/main.py`

**Step 1: Create `bot/logger.py`**

```python
import logging
import os

def setup_logging(data_dir: str):
    os.makedirs(os.path.join(data_dir, "logs"), exist_ok=True)

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s — %(message)s")

    file_handler = logging.FileHandler(os.path.join(data_dir, "logs", "bot.log"))
    file_handler.setFormatter(fmt)

    error_handler = logging.FileHandler(os.path.join(data_dir, "logs", "errors.log"))
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(fmt)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(error_handler)
    root.addHandler(stream_handler)
```

**Step 2: Update `bot/main.py` to use `setup_logging`**

Replace the `logging.basicConfig(...)` call with:
```python
from bot.logger import setup_logging
setup_logging(config.data_dir)
```

**Step 3: Commit**

```bash
git add bot/logger.py bot/main.py
git commit -m "feat: structured logging with separate error log"
```

---

## Task 13: Final Integration Test & Docker Build

**Step 1: Run full test suite**

```bash
pytest tests/ -v
```
Expected: all PASS

**Step 2: Build Docker image**

```bash
docker compose build
```
Expected: builds without errors

**Step 3: Smoke test with real credentials (optional, manual)**

```bash
cp .env.example .env
# fill in TELEGRAM_TOKEN and ANTHROPIC_API_KEY
docker compose up
```

Send `/start` to the bot on Telegram — verify admin detection works.

**Step 4: Final commit**

```bash
git add .
git commit -m "chore: final integration — all tests pass, docker build clean"
```

---

## Summary of Files Created

```
bot/__init__.py
bot/config.py
bot/db.py
bot/storage.py
bot/agent.py
bot/handler.py
bot/main.py
bot/logger.py
bot/scheduler.py
bot/oauth.py
bot/tools/__init__.py
bot/tools/registry.py
bot/tools/memory_tool.py
bot/tools/web_search.py
bot/tools/web_reader.py
bot/tools/wikipedia.py
bot/tools/youtube.py
bot/tools/arxiv.py
bot/tools/news.py
bot/tools/weather.py
bot/tools/currency.py
bot/tools/qrcode_tool.py
bot/tools/url_shortener.py
bot/tools/pdf_tool.py
bot/tools/google_calendar.py
bot/tools/gmail.py
bot/tools/google_drive.py
admin.py
setup.py
install.sh
Dockerfile
docker-compose.yml
.env.example
requirements.txt
tests/__init__.py
tests/conftest.py
tests/test_config.py
tests/test_db.py
tests/test_storage.py
tests/test_tools.py
tests/test_agent.py
tests/test_handler.py
tests/test_oauth.py
tests/test_scheduler.py
```
