#!/usr/bin/env python3
"""
Live E2E test: connects to Telegram via Telethon, sends messages to the bot,
captures all responses, and saves dialogs to files/live_test_YYYYMMDD_HHMMSS/.

Usage:
    python scripts/live_test.py --bot @YourBotUsername

Requirements in .env:
    TELEGRAM_API_ID=...
    TELEGRAM_API_HASH=...
    TELEGRAM_PHONE=+1234567890   # account to use for testing

Or pass as CLI args:
    python scripts/live_test.py --api-id 123 --api-hash abc --phone +1234 --bot @bot
"""
import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.tl.functions.contacts import ResolveUsernameRequest

load_dotenv()

TIMEOUT = 45  # seconds to wait for bot reply
PAUSE = 3.0   # seconds between messages

# ── Test suite ───────────────────────────────────────────────────────────────
# Each entry: (label, message_to_send)
TESTS = [
    # Basic commands
    ("start",           "/start"),
    ("help",            "/help"),

    # Formatting tests (Markdown/Telegram) - explicitly request Markdown
    ("format_bold_md",    'Reply using MarkdownV2: *bold text*'),
    ("format_italic_md",  'Reply using MarkdownV2: _italic text_'),
    ("format_code_md",    'Reply using MarkdownV2: `inline code`'),
    ("format_bold2_md",  'Reply using MarkdownV2: **bold with asterisks**'),
    ("format_mixed_md",   'Reply using MarkdownV2: Mix *bold*, _italic_, and `code`'),
    
    # Table formatting test
    ("table_md",        'Create a Markdown table with 3 columns: Name, City, Age. Add 3 rows of sample data.'),
    
    # Conversation
    ("hello",           "Hello! What can you do?"),
    ("math",            "What is 17 * 23?"),
    ("joke",            "Tell me a short joke"),

    # Web search
    ("web_search",      "Search the web: latest news about Claude AI"),

    # Wikipedia
    ("wikipedia",       "Wikipedia: Nikola Tesla"),

    # News
    ("news_general",    "новости"),
    ("news_topic",      "news about artificial intelligence"),

    # Weather
    ("weather",         "What's the weather in Berlin?"),

    # Currency
    ("currency",        "Convert 100 USD to EUR"),

    # YouTube transcript
    ("youtube",         "Summarize this video: https://www.youtube.com/watch?v=dQw4w9WgXcQ"),

    # YouTube search
    ("youtube_search",  "Find me a YouTube video about building AI agents in Python and summarize it"),

    # QR code
    ("qr_code",         "Generate a QR code for https://github.com"),

    # URL shortener
    ("url_shorten",     "Shorten this URL: https://www.google.com/search?q=telegram+bots"),

    # Flight search
    ("flights",         "Find cheapest flights BIO to MAD in April 2026"),

    # Memory
    ("memory_save",     "Remember that my favorite color is blue and I live in Berlin"),
    ("memory_recall",   "What do you know about me?"),

    # Skills
    ("skill_save",      'Save a skill called "daily_standup" with these instructions: Ask me what I did yesterday, what I plan to do today, and if I have any blockers'),
    ("skill_list",      "List my saved skills"),
    ("skill_use",       'Use the "daily_standup" skill'),

    # Reminders
    ("reminder_set",    "Remind me to drink water in 2 minutes"),
    ("reminder_list",   "/reminders"),

    # Log search
    ("log_search",      "Search my logs for 'water'"),

    # Email
    ("email_status",    "/status"),
    ("email_list",      "List my recent emails"),
    ("email_unread",    "Show me unread emails"),
    ("email_search",    "Search my emails for 'meeting'"),
    ("email_send",      "Send an email to test@example.com with subject 'Test' and body 'This is a test message'"),

    # Calendar
    ("calendar_status", "What calendar integrations do I have?"),
    ("calendar_list",   "Show me my calendar events for today"),
    ("calendar_upcoming", "What are my upcoming events this week?"),
    ("calendar_create", "Create a calendar event: Team meeting tomorrow at 2pm for 1 hour"),
    ("calendar_search", "Search my calendar for 'standup'"),

    # Cancel
    ("cancel",          "/cancel"),
]

# ── Helpers ──────────────────────────────────────────────────────────────────

class DialogRecorder:
    def __init__(self, out_dir: Path):
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.records: list[dict] = []

    def record(self, label: str, sent: str, replies: list[str], elapsed: float, error: str = ""):
        entry = {
            "label": label,
            "sent": sent,
            "replies": replies,
            "elapsed_s": round(elapsed, 2),
            "error": error,
            "ts": datetime.utcnow().isoformat(),
        }
        self.records.append(entry)
        # Print summary
        status = "✓" if not error else "✗"
        reply_preview = replies[0][:80].replace("\n", " ") if replies else "(no reply)"
        print(f"  {status} [{label}] → {reply_preview}")
        if error:
            print(f"    ERROR: {error}")

    def save(self):
        # Full JSON
        json_path = self.out_dir / "results.json"
        json_path.write_text(json.dumps(self.records, indent=2, ensure_ascii=False))

        # Human-readable markdown dialog
        md_path = self.out_dir / "dialog.md"
        lines = [f"# Live Bot Test — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n"]
        for r in self.records:
            status = "PASS" if not r["error"] else "FAIL"
            lines.append(f"## [{r['label']}] {status} ({r['elapsed_s']}s)\n")
            lines.append(f"**Sent:** `{r['sent']}`\n")
            for reply in r["replies"]:
                lines.append(f"**Bot:**\n```\n{reply}\n```\n")
            if r["error"]:
                lines.append(f"**Error:** {r['error']}\n")
            lines.append("")
        md_path.write_text("\n".join(lines), encoding="utf-8")

        # Summary table
        total = len(self.records)
        passed = sum(1 for r in self.records if not r["error"])
        print(f"\n{'─'*60}")
        print(f"Results saved to: {self.out_dir}")
        print(f"Passed: {passed}/{total}")
        print(f"Files: {json_path.name}, {md_path.name}")


async def wait_for_replies(client, bot_entity, timeout: float) -> list[str]:
    """Collect all messages from bot within timeout, stop when idle for 2s."""
    replies = []
    deadline = asyncio.get_event_loop().time() + timeout
    idle_deadline = None

    @client.on(events.NewMessage(from_users=bot_entity))
    async def handler(event):
        nonlocal idle_deadline
        text = event.raw_text or ""
        # Only treat as PHOTO if it's an actual uploaded photo (not a link preview)
        from telethon.tl.types import MessageMediaWebPage
        is_link_preview = isinstance(getattr(event.message, 'media', None), MessageMediaWebPage)
        if event.photo and not is_link_preview:
            text = f"[PHOTO] caption={event.message.message or '(none)'}"
        elif event.document:
            text = f"[DOCUMENT] {getattr(event.document, 'mime_type', '')} caption={event.message.message or '(none)'}"
        replies.append(text)
        idle_deadline = asyncio.get_event_loop().time() + 2.0

    try:
        while True:
            now = asyncio.get_event_loop().time()
            if now > deadline:
                break
            if idle_deadline and now > idle_deadline:
                break
            await asyncio.sleep(0.2)
    finally:
        client.remove_event_handler(handler)

    return replies


async def run_tests(client, bot_entity, recorder: DialogRecorder, tests):
    for label, message in tests:
        print(f"\n→ {label}: {message[:60]}")
        t0 = asyncio.get_event_loop().time()
        error = ""
        replies = []
        try:
            await client.send_message(bot_entity, message)
            replies = await wait_for_replies(client, bot_entity, TIMEOUT)
            if not replies:
                error = f"no reply within {TIMEOUT}s"
        except Exception as e:
            error = str(e)
        elapsed = asyncio.get_event_loop().time() - t0
        recorder.record(label, message, replies, elapsed, error)
        await asyncio.sleep(PAUSE)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-id",  default=os.getenv("TELEGRAM_API_ID"))
    parser.add_argument("--api-hash", default=os.getenv("TELEGRAM_API_HASH"))
    parser.add_argument("--phone",   default=os.getenv("TELEGRAM_PHONE"))
    parser.add_argument("--bot",     default=os.getenv("TELEGRAM_BOT_USERNAME", "@SuperPuperClaw_bot"))
    parser.add_argument("--out",     default="files/live_tests")
    parser.add_argument("--only",    nargs="*", help="Run only these test labels")
    parser.add_argument("--test-dc", action="store_true", default=os.getenv("TELEGRAM_TEST_DC", "").lower() in ("1", "true"),
                        help="Use Telegram test DC (149.154.167.40:443). Phone: +99966XXXXX, code: XXXXX")
    args = parser.parse_args()

    if not args.api_id or not args.api_hash:
        print("ERROR: Set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env or pass as args.")
        print("Get them at https://my.telegram.org/apps")
        sys.exit(1)

    if not args.phone:
        if args.test_dc:
            args.phone = os.getenv("TELEGRAM_PHONE", "+9996621234")
        else:
            print("ERROR: Set TELEGRAM_PHONE in .env or pass --phone")
            sys.exit(1)

    session_path = Path("files") / ("telethon_testdc_session" if args.test_dc else "telethon_test_session")
    session_path.parent.mkdir(exist_ok=True)

    out_dir = Path(args.out) / datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    if args.test_dc:
        client = TelegramClient(str(session_path), int(args.api_id), args.api_hash,
                                server=("149.154.167.40", 443))
    else:
        client = TelegramClient(str(session_path), int(args.api_id), args.api_hash)

    print(f"Connecting as {args.phone} ({'test DC' if args.test_dc else 'production'})...")
    await client.start(phone=args.phone)
    print("Connected.")

    # Resolve bot
    bot_username = args.bot.lstrip("@")
    result = await client(ResolveUsernameRequest(bot_username))
    bot_entity = result.users[0]
    print(f"Bot: @{bot_entity.username} (id={bot_entity.id})")

    tests_to_run = TESTS
    if args.only:
        tests_to_run = [(l, m) for l, m in TESTS if l in args.only]
        if not tests_to_run:
            print(f"ERROR: no tests matched: {args.only}")
            sys.exit(1)

    recorder = DialogRecorder(out_dir)
    print(f"\nRunning {len(tests_to_run)} tests against @{bot_entity.username}...\n{'─'*60}")

    try:
        await run_tests(client, bot_entity, recorder, tests_to_run)
    finally:
        recorder.save()
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
