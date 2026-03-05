# Telegram AI Assistant — Design Document

**Date:** 2026-03-03
**Status:** Approved

---

## Overview

A multi-user personal AI assistant Telegram bot. Users interact naturally via chat; the agent selects and executes tools on their behalf. User data is fully isolated. Deployed as a single Docker container on a Linux VPS.

---

## Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| AI agent | Anthropic Agent SDK |
| Telegram | python-telegram-bot (polling) |
| Persistence | SQLite (per-user) |
| Scheduling | APScheduler |
| OAuth callback | aiohttp (internal) |
| Voice transcription | faster-whisper (local) |
| Deployment | Docker + docker-compose |

---

## Project Structure

```
/
├── bot/
│   ├── main.py              # entry point
│   ├── handler.py           # Telegram message/command handlers
│   ├── agent.py             # Anthropic Agent SDK runner
│   ├── memory.py            # read/write memory.md per user
│   ├── scheduler.py         # APScheduler, reminder jobs
│   ├── oauth.py             # OAuth callback server (aiohttp)
│   └── tools/
│       ├── web_search.py    # duckduckgo-search
│       ├── web_reader.py    # httpx + BeautifulSoup
│       ├── wikipedia.py
│       ├── youtube.py       # youtube-transcript-api
│       ├── arxiv.py
│       ├── news.py          # RSS feeds
│       ├── weather.py       # Open-Meteo
│       ├── currency.py      # frankfurter.app
│       ├── whisper.py       # faster-whisper
│       ├── pdf.py           # pypdf
│       ├── qrcode.py
│       ├── url_shortener.py
│       ├── google_calendar.py
│       ├── gmail.py
│       └── google_drive.py
├── data/                    # Docker volume (persisted)
│   ├── global.db            # all users, auth state
│   ├── logs/
│   │   ├── bot.log
│   │   └── errors.log
│   └── users/
│       └── <telegram_id>/
│           ├── memory.md
│           ├── conversations.db
│           └── oauth_tokens.json
├── setup.py                 # interactive setup script
├── admin.py                 # CLI admin tool
├── install.sh               # curl-based one-liner installer
├── Dockerfile
├── docker-compose.yml
└── .env
```

---

## Data Model

### `/data/global.db`

```sql
users(
  telegram_id  INTEGER PRIMARY KEY,
  username     TEXT,
  status       TEXT,  -- pending | approved | banned
  is_admin     INTEGER DEFAULT 0,
  created_at   TEXT
)
```

### `/data/users/<telegram_id>/conversations.db`

```sql
messages(id, role, content, timestamp)
jobs(id, cron, description, next_run, active)
user(id, status, is_admin, created_at)
```

### `/data/users/<telegram_id>/memory.md`

Free-text file maintained by Claude. Written via `memory_update` tool call. Read in full at the start of every conversation.

```markdown
- Name: Alex
- Timezone: Europe/London
- Prefers concise bullet responses
- Has standup every Monday 9am
```

### `/data/users/<telegram_id>/oauth_tokens.json`

```json
{
  "token": "...",
  "refresh_token": "...",
  "expiry": "2026-04-01T12:00:00Z"
}
```

---

## User Isolation

- Every message: `telegram_id` extracted → checked against `global.db` before any action
- File paths always built server-side from verified `telegram_id` — never from user input
- Agent tool registry scoped to current user only — no cross-user API exists
- Per-user SQLite files — no shared connections
- `/data` volume only accessible inside Docker container

---

## Agent Execution Flow

```
Telegram message
       ↓
1. Auth check (global.db — status == approved?)
       ↓
2. Load context:
   - memory.md (full)
   - last N messages from conversations.db
       ↓
3. Build system prompt:
   - user facts from memory.md
   - current date/time in user's timezone
   - available tools
       ↓
4. Run Anthropic Agent SDK
   - Claude selects and calls tools
   - results returned, Claude may chain tool calls
       ↓
5. Save user message + assistant response to conversations.db
       ↓
6. Optionally update memory.md (if Claude called memory_update)
       ↓
7. Send response to Telegram
```

**Slow tools** (Whisper, large PDFs): dispatched as asyncio background tasks. Bot sends acknowledgement immediately, sends result when ready — no user polling needed.

**Voice messages**: Telegram `.ogg` → downloaded → faster-whisper → transcript fed to agent as text.

---

## Tools

### Stateless
| Tool | Library / API |
|---|---|
| Web search | duckduckgo-search |
| Web reader | httpx + BeautifulSoup |
| Wikipedia | wikipedia |
| YouTube transcripts | youtube-transcript-api |
| arXiv search | arxiv |
| News digest | feedparser (RSS) |
| Weather | Open-Meteo (no key) |
| Currency conversion | frankfurter.app (no key) |
| QR code | qrcode (local) |
| URL shortener | tinyurl.com (no key) |
| PDF summary | pypdf (local) |
| Voice transcription | faster-whisper (local) |
| Gmail | google-api-python-client |
| Google Calendar | google-api-python-client |
| Google Drive | google-api-python-client |

### Stateful
| Tool | State | Location |
|---|---|---|
| Reminders | job definitions | `jobs` table |
| Google OAuth | tokens | `oauth_tokens.json` |
| Memory update | user facts | `memory.md` |
| Conversation | message history | `messages` table |

---

## Access Control

- **Registration:** users send `/start` → status set to `pending`
- **Approval:** admin receives notification, runs `/approve <telegram_id>` or uses `botadmin` CLI
- **Admin:** first user to send `/start` after fresh install is automatically set as admin
- **Blocking/banning:** via `botadmin` CLI

---

## Google Integration

- **OAuth app:** one shared Google Cloud project (admin sets up once — Gmail API, Calendar API, Drive API enabled)
- **Per-user auth flow:**
  1. User types `/connect google`
  2. Bot sends Google auth URL
  3. User authorizes in browser, copies redirect URL, pastes back to bot
  4. Bot extracts auth code, exchanges for tokens, saves to `oauth_tokens.json`
- **Token refresh:** silent refresh on each Google API call; if refresh fails → prompt user to reconnect

---

## Setup & Deployment

### One-liner install
```bash
curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/main/install.sh | bash
```

`install.sh` checks dependencies (docker, docker compose, git), clones repo, runs `setup.py`.

### Interactive setup (`setup.py`)
1. Enter Telegram Bot Token → validated via Telegram API
2. Enter Anthropic API Key → validated
3. Google integration (optional) → enter Client ID + Secret
4. Admin detection → "Send any message to the bot, then press Enter" → auto-detects `telegram_id`
5. Writes `.env`, initializes `global.db` with admin user
6. Starts `docker compose up -d`

### Environment variables (`.env`)
```
TELEGRAM_TOKEN=
ANTHROPIC_API_KEY=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
```

### Admin CLI
```bash
botadmin   # alias set during install
```

Menus:
- **Status & Stats** — uptime, user counts, messages today, API cost estimate
- **Users** — list all/pending, approve, ban, delete + data, view memory
- **Jobs** — list and cancel scheduled reminders
- **Logs** — recent logs, errors only, search by user (browse list or type ID)
- **System** — view logs, restart bot

---

## Error Handling

| Scenario | User message | Admin notification |
|---|---|---|
| Tool failure | "X is unavailable right now" | No |
| Google token expired | "Reconnect Google with /connect google" | No |
| Anthropic rate limit | "I'm busy, please wait a moment" | No |
| Anthropic auth/billing error | "Something went wrong" | Yes — Telegram DM |
| Reminder delivery failure | Notified on next message (after 3 failures) | No |
| Unhandled exception | "Something went wrong, please try again" | Yes — Telegram DM |

All errors logged to `/data/logs/errors.log`. Accessible via `botadmin` → Logs.

---

## Scaling

**Comfortable capacity on 2 CPU / 4GB VPS:**
- ~50–100 active users
- ~10 simultaneous conversations
- Voice transcriptions queue (faster-whisper is CPU-bound)

**v2 scaling path (if needed):**
- Redis + Celery worker queue for slow tools
- PostgreSQL for global DB
- Multiple bot worker processes + Telegram webhook

---

## User Commands

```
/start        — register / welcome message
/help         — list features and available tools
/connect google — link Google account
/status       — show connected integrations
```

All other interactions via natural language.
