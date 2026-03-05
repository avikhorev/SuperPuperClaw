# SuperPuperClaw

A self-hosted, multi-user personal AI assistant for Telegram. Users chat naturally; the agent picks and runs tools on their behalf. All user data is fully isolated. Runs as a single Docker container on any Linux VPS.

## Features

- **AI agent** powered by Claude (Anthropic API) with tool use
- **Per-user memory** — Claude maintains a `memory.md` of facts about each user
- **Conversation history** — last N messages carried as context
- **Voice messages** — transcribed locally via faster-whisper
- **PDF processing** — extract and summarise PDF content
- **Reminders** — set recurring or one-off reminders in natural language

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
| QR code generator | qrcode (local) |
| URL shortener | tinyurl.com |

### Optional integrations

- **Google** — Gmail, Calendar, Drive (one shared OAuth app, per-user auth)
- **Email (IMAP/SMTP)** — works with Gmail, Outlook, Yahoo, iCloud, Fastmail, and others; bot auto-detects server settings from email address
- **Calendar (ICS)** — read any public or private ICS URL (Google Calendar, Apple Calendar, Outlook, etc.)

## Requirements

- Docker + Docker Compose
- A [Telegram bot token](https://t.me/BotFather)
- An [Anthropic API key](https://console.anthropic.com/)
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

`setup.py` will ask for your Telegram token and Anthropic key, optionally configure Google OAuth, detect your Telegram ID as the admin, and write `.env`.

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
/start          — register (first user becomes admin)
/help           — list features and available tools
/connect google — link Google account (Gmail, Calendar, Drive)
/connect email  — link email via IMAP (Gmail, Outlook, Yahoo, iCloud, …)
/connect calendar — link a calendar via ICS URL
/status         — show connected integrations
```

All other interactions are natural language.

## Google integration (optional)

1. Create a Google Cloud project and enable Gmail API, Calendar API, and Drive API
2. Create OAuth 2.0 credentials (Desktop app / installed type), download the client secret
3. Enter `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env` (or during setup)
4. Users connect via `/connect google` — bot sends an auth URL, user pastes back the redirect URL

## Project structure

```
bot/
├── main.py          # entry point
├── handler.py       # Telegram handlers
├── agent.py         # Claude tool-use loop
├── db.py            # GlobalDB + UserDB (SQLite)
├── storage.py       # per-user file storage
├── scheduler.py     # APScheduler reminders
├── oauth.py         # Google OAuth flow
├── imap_providers.py # IMAP/SMTP server auto-detection
├── logger.py
└── tools/           # all tool implementations
data/                # Docker volume (persisted)
├── global.db
├── logs/
└── users/<telegram_id>/
    ├── memory.md
    ├── conversations.db
    └── oauth_tokens.json
```

## License

MIT
