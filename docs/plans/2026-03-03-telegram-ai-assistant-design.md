# Telegram AI Assistant — Design Document

**Date:** 2026-03-03
**Last updated:** 2026-03-07
**Status:** Implemented

---

## Overview

A multi-user personal AI assistant Telegram bot. Users interact naturally via chat; the agent selects and executes tools on their behalf. User data is fully isolated. Deployed as a single Docker container on a Linux VPS.

---

## Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| AI agent | Anthropic Agent SDK (`claude_agent_sdk`) |
| Telegram | python-telegram-bot (polling) |
| Persistence | SQLite (per-user) |
| Scheduling | APScheduler |
| Voice transcription | faster-whisper (local) |
| Deployment | Docker + docker-compose |

---

## Project Structure

```
/
├── bot/
│   ├── main.py              # entry point, scheduler setup, command menu
│   ├── handler.py           # Telegram message/command handlers
│   ├── agent.py             # Anthropic Agent SDK runner, system prompt builder
│   ├── storage.py           # per-user file storage (memory, logs, skills, configs)
│   ├── db.py                # GlobalDB + UserDB (SQLite)
│   ├── scheduler.py         # APScheduler reminders + cron parsing
│   ├── heartbeat.py         # daily proactive digest runner
│   ├── imap_providers.py    # IMAP/SMTP auto-detection by email domain
│   ├── logger.py
│   └── tools/
│       ├── registry.py         # assembles tool list per user
│       ├── memory_tool.py      # update_profile, update_context
│       ├── heartbeat_tool.py   # read_heartbeat, update_heartbeat
│       ├── logs_tool.py        # search_logs
│       ├── skills_tool.py      # save_skill, read_skill, list_skills
│       ├── reminders.py        # set_reminder, list_reminders, cancel_reminder
│       ├── imap_email.py       # read/send email via IMAP/SMTP
│       ├── caldav_calendar.py  # read/write calendar via CalDAV
│       ├── ics_calendar.py     # read-only calendar via ICS URL
│       ├── web_search.py       # DuckDuckGo HTML scrape (geo-routing bypass)
│       ├── web_reader.py       # httpx + BeautifulSoup
│       ├── wikipedia.py
│       ├── youtube.py          # youtube-transcript-api
│       ├── arxiv.py
│       ├── news.py             # RSS feeds (feedparser)
│       ├── weather.py          # Open-Meteo (no key)
│       ├── currency.py         # frankfurter.app (no key)
│       ├── flights.py          # link builder (Kiwi/Google Flights)
│       ├── pdf_tool.py         # pypdf
│       ├── qrcode_tool.py      # api.qrserver.com → sent as photo by handler
│       └── url_shortener.py    # tinyurl.com
├── data/                    # Docker volume (persisted)
│   ├── global.db
│   └── users/
│       └── <telegram_id>/
│           ├── conversations.db
│           ├── memory/
│           │   ├── profile.md      # stable user facts
│           │   ├── context.md      # working state / current projects
│           │   ├── agent.md        # behavior rules (seeded from DEFAULT_AGENT_RULES)
│           │   └── heartbeat.md    # daily digest instructions
│           ├── logs/
│           │   └── YYYY-MM-DD.md
│           ├── skills/
│           │   └── <name>.md
│           ├── imap_config.json
│           └── caldav_config.json
├── setup.py
├── admin.py
├── install.sh
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
jobs(id, cron, description, next_run, active, fail_count)
```

---

## Memory System

| File | Tool(s) | Purpose |
|---|---|---|
| `memory/profile.md` | `update_profile` | Stable facts: name, timezone, preferences |
| `memory/context.md` | `update_context` | Working state: projects, ongoing tasks |
| `memory/agent.md` | _(read-only)_ | Behavior rules — seeded from `DEFAULT_AGENT_RULES` |
| `memory/heartbeat.md` | `read_heartbeat`, `update_heartbeat` | Daily digest instructions |
| `logs/YYYY-MM-DD.md` | `search_logs` | Full conversation history, searchable |
| `skills/<name>.md` | `save_skill`, `read_skill`, `list_skills` | Named reusable instruction sets |

---

## Agent Execution Flow

```
Telegram message
       ↓
1. Auth check (global.db — status == approved?)
       ↓
2. Load context: profile.md + context.md + agent.md + last 20 messages
       ↓
3. Build system prompt (current date/time + memory + tool list)
       ↓
4. Run Anthropic Agent SDK (Claude selects and chains tool calls)
       ↓
5. Save to conversations.db + append to logs/YYYY-MM-DD.md
       ↓
6. Send response (PHOTO_FILE:/path or PHOTO_URL:url → sent as photo; else text)
```

Voice messages: Telegram `.ogg` → faster-whisper → transcript → agent.

---

## Tools

### Built-in (no keys required)

| Tool | Source |
|---|---|
| Web search | DuckDuckGo HTML lite (`kl=us-en` bypasses geo-routing) |
| Web reader | httpx + BeautifulSoup |
| Wikipedia | wikipedia |
| YouTube transcripts | youtube-transcript-api *(blocked from cloud IPs by YouTube)* |
| arXiv search | arxiv |
| News digest | RSS/feedparser (BBC, NYT, Lenta, RBC, Spiegel, DW) |
| Weather | Open-Meteo |
| Currency conversion | frankfurter.app |
| QR code | api.qrserver.com → photo |
| URL shortener | tinyurl.com |
| PDF summary | pypdf |
| Flights | booking link builder |
| Log search | full-text grep over daily logs |
| Skills | save/read/list named `.md` files |
| Reminders | APScheduler cron jobs, persisted in SQLite |

### Optional integrations

| Integration | Config |
|---|---|
| Email (IMAP/SMTP) | `imap_config.json` — auto-detected from email domain |
| Calendar read/write (CalDAV) | `caldav_config.json` |
| Calendar read-only (ICS URL) | `caldav_config.json` |

---

## Access Control

- **Registration:** `/start` → status `pending`
- **Approval:** admin via `botadmin` CLI
- **Admin:** first user after fresh install auto-promoted
- **Blocking:** via `botadmin` CLI

---

## Environment Variables

```
TELEGRAM_TOKEN=
ANTHROPIC_API_KEY=
```

No Google OAuth, no cloud service keys required.

---

## Known Limitations

- **YouTube transcripts:** YouTube blocks cloud server IPs. Bot falls back to summarising from search snippets.
- **Web search geo-routing:** DDG JSON API returns region-locked results; fixed via HTML lite endpoint.
- **Flight prices:** VPS geo returns non-English results; bot provides booking links instead of live prices.
