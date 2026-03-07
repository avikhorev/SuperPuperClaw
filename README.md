# SuperPuperClaw

A self-hosted, multi-user personal AI assistant for Telegram. Users chat naturally; the agent picks and runs tools on their behalf. All user data is fully isolated. Runs as a single Docker container on any Linux VPS.

## Features

- **AI agent** powered by Claude (Anthropic API or Claude subscription via CLI) with tool use
- **Structured memory** — per-user `profile.md`, `context.md`, and `agent.md` (behavior rules)
- **Daily session logs** — every exchange appended to `logs/YYYY-MM-DD.md`; searchable via `search_logs` tool
- **Skills registry** — save and reuse named instruction sets (`save_skill`, `read_skill`, `list_skills`)
- **Heartbeat** — configurable daily proactive digest (edit via `update_heartbeat`)
- **Reminders** — set recurring reminders in natural language (`set_reminder`, `list_reminders`, `cancel_reminder`)
- **Conversation history** — last 20 messages carried as context
- **Voice messages** — transcribed locally via faster-whisper
- **PDF processing** — extract and summarise PDF content
- **QR codes** — generated and sent as images

### Built-in tools (no API keys required)

| Tool | Source |
|---|---|
| Web search | DuckDuckGo |
| Web reader | httpx + BeautifulSoup |
| Wikipedia | wikipedia |
| YouTube transcripts | youtube-transcript-api |
| arXiv search | arxiv |
| News digest | RSS (feedparser) |
| Weather | Open-Meteo |
| Currency conversion | frankfurter.app |
| QR code generator | api.qrserver.com (sent as image) |
| URL shortener | tinyurl.com |
| Log search | full-text search over daily logs |
| Skills | save/read/list named instruction files |
| Reminders | APScheduler cron jobs, persisted in SQLite |

### Optional integrations

- **Email (IMAP/SMTP)** — works with Gmail, Outlook, Yahoo, iCloud, Fastmail, and others; bot auto-detects server settings from email address
- **Calendar (CalDAV)** — read/write via CalDAV (iCloud, Fastmail, Outlook, Google)
- **Calendar (ICS)** — read-only via any public or private ICS URL

## Requirements

- Docker + Docker Compose
- A [Telegram bot token](https://t.me/BotFather)
- A Claude subscription or [Anthropic API key](https://console.anthropic.com/) (authenticated via `claude` CLI)
- A Linux VPS (2 CPU / 4 GB RAM comfortable for ~50–100 active users)

## Quick install

```bash
curl -fsSL https://raw.githubusercontent.com/avikhorev/SuperPuperClaw/main/install.sh | bash
```

This will:
1. Check for Docker and Git
2. Install Node.js + Claude Code CLI if needed
3. Clone the repo
4. Run the interactive setup (`setup.py`)
5. Start the bot and prompt for Claude account login
6. Add `botadmin` and `botauth` shell aliases

### Re-authenticating Claude Code

If credentials expire or the volume is lost:

```bash
botauth
```

Or directly: `docker compose exec -it bot claude auth login`

## Manual setup

```bash
git clone https://github.com/avikhorev/SuperPuperClaw.git
cd SuperPuperClaw
python setup.py
docker compose up -d
```

`setup.py` will ask for your Telegram token, optionally configure a Webshare proxy (for YouTube transcripts), detect your Telegram ID as the admin, and write `.env`.

## Admin CLI

```bash
botadmin
```

Or directly: `docker compose exec bot python admin.py`

Menu options:
- **Status & Stats** — uptime, user counts, messages today, API cost estimate
- **Users** — list all / pending, approve, ban, delete data, view memory
- **Jobs** — list and cancel scheduled reminders
- **Logs** — recent logs, errors only, search by user

## User commands

```
/start            — register (first user becomes admin)
/help             — list features and available tools
/connect email    — link email via IMAP (Gmail, Outlook, Yahoo, iCloud, …)
/connect caldav   — link calendar read/write (iCloud, Fastmail, Outlook, Google)
/connect calendar — link calendar read-only via ICS URL
/cancel           — cancel any ongoing setup flow
/status           — show connected integrations
```

All other interactions are natural language.

## Memory system

Each user has memory files the agent reads and updates automatically:

| File | Tool | Purpose |
|---|---|---|
| `memory/profile.md` | `update_profile` | Stable facts: name, timezone, preferences |
| `memory/context.md` | `update_context` | Working state: current projects, ongoing tasks |
| `memory/agent.md` | _(read-only)_ | Behavior rules: tone, response style |
| `memory/heartbeat.md` | `read_heartbeat`, `update_heartbeat` | Daily proactive digest instructions |

Session logs are written to `logs/YYYY-MM-DD.md` and searchable via `search_logs`.

Skills are stored in `skills/<name>.md` and managed via `save_skill` / `read_skill` / `list_skills`.

## Project structure

```
bot/
├── main.py             # entry point, scheduler setup
├── handler.py          # Telegram command and message handlers
├── agent.py            # Claude agent loop (tool-use via claude_agent_sdk)
├── db.py               # GlobalDB + UserDB (SQLite)
├── storage.py          # per-user file storage (memory, logs, skills)
├── scheduler.py        # APScheduler reminders + cron parsing
├── heartbeat.py        # daily proactive digest runner
├── imap_providers.py   # IMAP/SMTP auto-detection by email domain
├── logger.py
└── tools/
    ├── registry.py       # assembles tool list per user
    ├── memory_tool.py    # update_profile, update_context
    ├── heartbeat_tool.py # read_heartbeat, update_heartbeat
    ├── logs_tool.py      # search_logs
    ├── skills_tool.py    # save_skill, read_skill, list_skills
    ├── reminders.py      # set_reminder, list_reminders, cancel_reminder
    ├── imap_email.py
    ├── caldav_calendar.py
    ├── ics_calendar.py
    ├── web_search.py
    ├── weather.py
    ├── qrcode_tool.py    # returns photo URL → sent as image by handler
    └── ...
data/                   # Docker volume (persisted)
├── global.db
└── users/<telegram_id>/
    ├── conversations.db
    ├── memory/
    │   ├── profile.md
    │   ├── context.md
    │   ├── agent.md
    │   └── heartbeat.md
    ├── logs/
    │   └── YYYY-MM-DD.md
    └── skills/
        └── <name>.md
```

## Testing

```bash
# Unit + integration tests (no credentials needed)
pytest tests/ --ignore=tests/e2e --ignore=tests/live -v

# Live Claude tests (requires API key or claude CLI)
pytest tests/live/ -v

# Full-stack tests (fake Telegram + real Claude)
pytest tests/e2e/test_e2e_full_stack.py -v

# Telegram test-server E2E (requires test DC credentials from my.telegram.org)
TG_TEST_API_ID=... TG_TEST_API_HASH=... bash scripts/run_testserver_e2e.sh
```

## Uninstall

Stop and remove the container, image, and network:

```bash
cd SuperPuperClaw
docker compose down --rmi all
```

To also delete all user data (messages, memory, credentials):

```bash
docker compose down --rmi all --volumes
```

Then remove the repo and shell aliases:

```bash
cd ~ && rm -rf SuperPuperClaw
sed -i '/botadmin\|botauth/d' ~/.bashrc ~/.zshrc 2>/dev/null || true
```

## License

MIT
