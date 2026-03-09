import asyncio
import logging
import os as _os
import tempfile as _tempfile
from functools import partial

from telegram import Update
from telegram.ext import ContextTypes

from bot.db import GlobalDB
from bot.storage import UserStorage
from bot.agent import AgentRunner
from bot.tools.registry import build_tool_registry
from bot.tools.memory_tool import update_profile, update_context

logger = logging.getLogger(__name__)

import re as _re

_PHOTO_FILE_TOKEN = _re.compile(r"PHOTO_FILE:(\S+)")
_PHOTO_URL_TOKEN  = _re.compile(r"PHOTO_URL:(\S+)")
_MARKDOWN_IMAGE   = _re.compile(r"!\[[^\]]*\]\((https?://\S+?)\)")

_MARKDOWN_TABLE   = _re.compile(r"^\|.+\|$", _re.MULTILINE)

_MARKDOWN_V2_SPECIAL = _re.compile(r'([!\[\\\]\(\)\{\}])')


def _escape_markdown_v2(text: str) -> str:
    """Escape special characters for MarkdownV2 (but not formatting chars like * _ ~ `)."""
    return _MARKDOWN_V2_SPECIAL.sub(r'\\\1', text)


_TMPDIR = _os.path.realpath(_tempfile.gettempdir())


def _safe_photo_path(path: str) -> str | None:
    """Return realpath only if it's inside the system temp directory; else None."""
    try:
        real = _os.path.realpath(path)
        if real.startswith(_TMPDIR + _os.sep) or real.startswith(_TMPDIR):
            return real
    except Exception:
        pass
    return None


def _extract_photos(text: str):
    """Return (list_of_photo_refs, cleaned_caption). photo_ref is a path or URL."""
    photos = []
    for path in _PHOTO_FILE_TOKEN.findall(text):
        safe = _safe_photo_path(path)
        if safe:
            photos.append(("file", safe))
        else:
            logger.warning("Rejected PHOTO_FILE path outside tmpdir: %s", path)
    for url in _PHOTO_URL_TOKEN.findall(text):
        photos.append(("url", url))
    for url in _MARKDOWN_IMAGE.findall(text):
        photos.append(("url", url))
    caption = _PHOTO_FILE_TOKEN.sub("", _PHOTO_URL_TOKEN.sub("", _MARKDOWN_IMAGE.sub("", text))).strip()
    return photos, caption


_QR_RESPONSE = _re.compile(
    r'''^QR code for\s+(?:the\s+)?(?:text\s+|URL\s+)?["«»""]?(.+?)["»""]?\.?\s*$''',
    _re.IGNORECASE | _re.DOTALL,
)


def _auto_generate_qr(text: str) -> str:
    """If Claude responded with 'QR code for X' without calling the tool, do it now."""
    clean = _re.sub(r"\*\*", "", text.strip())  # strip markdown bold
    m = _QR_RESPONSE.match(clean)
    if not m:
        return text
    from bot.tools.qrcode_tool import generate_qr
    result = generate_qr(m.group(1).strip())
    if result.startswith("PHOTO_FILE:"):
        return result  # return the token so _extract_photos handles it
    return text  # fallback to original text if generation failed


def _convert_markdown_tables(text: str) -> str:
    """Convert Markdown tables to aligned triple backticks for monospace rendering."""
    lines = text.split('\n')
    result = []
    in_table = False
    table_lines = []

    for line in lines:
        if _MARKDOWN_TABLE.match(line.strip()):
            if not in_table:
                in_table = True
                table_lines = []
            table_lines.append(line.strip())
        else:
            if in_table:
                if len(table_lines) >= 2:
                    # Calculate column widths
                    col_widths = []
                    for row in table_lines:
                        cells = [c.strip() for c in row.split('|') if c.strip()]
                        for i, cell in enumerate(cells):
                            if i >= len(col_widths):
                                col_widths.append(len(cell))
                            else:
                                col_widths[i] = max(col_widths[i], len(cell))
                    
                    # Reconstruct aligned table
                    aligned_rows = []
                    for row in table_lines:
                        cells = [c.strip() for c in row.split('|') if c.strip()]
                        aligned_cells = [cell.ljust(col_widths[i]) for i, cell in enumerate(cells)]
                        aligned_rows.append('| ' + ' | '.join(aligned_cells) + ' |')
                    
                    table_str = "```\n" + '\n'.join(aligned_rows) + "\n```"
                    result.append(table_str)
                in_table = False
                table_lines = []
            result.append(line)

    if in_table and len(table_lines) >= 2:
        col_widths = []
        for row in table_lines:
            cells = [c.strip() for c in row.split('|') if c.strip()]
            for i, cell in enumerate(cells):
                if i >= len(col_widths):
                    col_widths.append(len(cell))
                else:
                    col_widths[i] = max(col_widths[i], len(cell))
        
        aligned_rows = []
        for row in table_lines:
            cells = [c.strip() for c in row.split('|') if c.strip()]
            aligned_cells = [cell.ljust(col_widths[i]) for i, cell in enumerate(cells)]
            aligned_rows.append('| ' + ' | '.join(aligned_cells) + ' |')
        
        table_str = "```\n" + '\n'.join(aligned_rows) + "\n```"
        result.append(table_str)

    return "\n".join(result)


async def _send_reply(message, text: str):
    """Send reply, extracting PHOTO_FILE:/PHOTO_URL: tokens and sending as photos."""
    text = _auto_generate_qr(text)
    text = _convert_markdown_tables(text)
    photos, caption = _extract_photos(text)
    for i, (kind, ref) in enumerate(photos):
        cap = caption if i == 0 else None
        try:
            if kind == "file":
                with open(ref, "rb") as f:
                    await message.reply_photo(f, caption=cap)
                _os.unlink(ref)
            else:
                await message.reply_photo(ref, caption=cap)
        except Exception as e:
            logger.error("Failed to send photo %s: %s", ref, e)
    if not photos:
        await message.reply_text(_escape_markdown_v2(text), parse_mode="MarkdownV2")


async def _send_reply_to_chat(bot, chat_id: int, text: str):
    """Like _send_reply but using bot.send_* directly."""
    text = _convert_markdown_tables(text)
    text = _escape_markdown_v2(text)
    photos, caption = _extract_photos(text)
    for i, (kind, ref) in enumerate(photos):
        cap = caption if i == 0 else None
        try:
            if kind == "file":
                with open(ref, "rb") as f:
                    await bot.send_photo(chat_id=chat_id, photo=f, caption=cap)
                _os.unlink(ref)
            else:
                await bot.send_photo(chat_id=chat_id, photo=ref, caption=cap)
        except Exception as e:
            logger.error("Failed to send photo %s: %s", ref, e)
    if not photos:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="MarkdownV2")


def _build_help_text(config, storage) -> str:
    has_imap = storage.load_imap_config() is not None
    has_ics = storage.load_calendar_config() is not None
    has_caldav = storage.load_caldav_config() is not None

    lines = ["*Your personal AI assistant*\n"]

    # --- Capabilities ---
    lines.append("*What I can do:*")

    if has_imap:
        lines.append("📧 Email — read, reply, send, delete, mark read")
    if has_caldav:
        lines.append("📅 Calendar — list, create, update, delete events")
    elif has_ics:
        lines.append("📅 Calendar — list upcoming events (read-only)")
    lines.append("🔍 Web search, page summaries, Wikipedia, arXiv, YouTube")
    lines.append("📰 News digest")
    lines.append("🌤 Weather & currency conversion")
    lines.append("🔗 QR codes, URL shortener")
    lines.append("📄 PDF summaries — just send a PDF")
    lines.append("🎙 Voice messages — I'll transcribe and respond")

    # --- Commands ---
    lines.append("\n*Commands:*")
    lines.append("/help — this message")
    lines.append("/cancel — cancel any ongoing setup")
    lines.append("/status — show connected integrations")
    lines.append("/connect email you@example.com — link email")
    lines.append("/connect caldav you@example.com — link calendar (read/write)")
    lines.append("/connect calendar — link calendar read-only (ICS URL)")

    lines.append("\nJust talk to me naturally — no commands needed!")
    return "\n".join(lines)


class BotHandler:
    def __init__(self, config, global_db: GlobalDB, scheduler=None):
        self.config = config
        self.global_db = global_db
        self.scheduler = scheduler

    def _get_storage(self, telegram_id: int) -> UserStorage:
        return UserStorage(data_dir=self.config.data_dir, telegram_id=telegram_id)

    def _get_runner(self, storage: UserStorage, telegram_id: int = None) -> AgentRunner:
        tools = build_tool_registry(storage, scheduler=self.scheduler, telegram_id=telegram_id)
        for fn in (update_profile, update_context):
            bound = partial(fn, storage=storage)
            bound.__name__ = fn.__name__
            bound.__doc__ = fn.__doc__
            bound._needs_storage = False
            tools.append(bound)
        from bot.tools.heartbeat_tool import build_heartbeat_tools
        tools += build_heartbeat_tools(storage)
        return AgentRunner(storage=storage, tools=tools)

    async def start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        username = update.effective_user.username or ""
        self.global_db.register_user(telegram_id=uid, username=username)
        user = self.global_db.get_user(uid)

        if user["is_admin"]:
            await update.message.reply_text(
                "Welcome! You're the admin. The bot is ready.\n\n"
                "Use /help to see what I can do."
            )
        else:
            admin = self.global_db.get_admin()
            if admin:
                try:
                    await ctx.bot.send_message(
                        chat_id=admin["telegram_id"],
                        text=f"New user request: @{username} (id: {uid})\n"
                             f"Approve: /approve {uid}  |  Ban: /ban {uid}"
                    )
                except Exception:
                    pass
            await update.message.reply_text(
                "Hi! Access is by approval only. Your request has been sent to the admin."
            )

    async def help_command(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        user = self.global_db.get_user(uid)
        if not user or user["status"] != "approved":
            return
        storage = self._get_storage(uid)
        text = _build_help_text(self.config, storage)
        await update.message.reply_text(text, parse_mode="Markdown")

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

    async def cancel_command(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        ctx.user_data.clear()
        await update.message.reply_text("Cancelled.")

    async def reminders_command(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        user = self.global_db.get_user(uid)
        if not user or user["status"] != "approved":
            return
        storage = self._get_storage(uid)
        jobs = storage.db.list_active_jobs()
        if not jobs:
            await update.message.reply_text("No active reminders.")
        else:
            lines = [f"[{j['id']}] {j['description']} ({j['cron']})" for j in jobs]
            await update.message.reply_text("Active reminders:\n" + "\n".join(lines))

    async def status_command(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        user = self.global_db.get_user(uid)
        if not user or user["status"] != "approved":
            return
        storage = self._get_storage(uid)
        lines = []

        imap_cfg = storage.load_imap_config()
        email_status = f"✅ {imap_cfg['email']}" if imap_cfg else "❌ Not connected — use /connect email"
        lines.append(f"Email: {email_status}")

        caldav_cfg = storage.load_caldav_config()
        cal_cfg = storage.load_calendar_config()
        if caldav_cfg:
            lines.append("Calendar: ✅ CalDAV (read/write)")
        elif cal_cfg:
            lines.append("Calendar: ✅ ICS (read-only) — use /connect caldav for write access")
        else:
            lines.append("Calendar: ❌ Not connected — use /connect caldav or /connect calendar")

        await update.message.reply_text("\n".join(lines))

    async def connect_command(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        user = self.global_db.get_user(uid)
        if not user or user["status"] != "approved":
            return

        args = ctx.args or []
        subcommand = args[0].lower() if args else ""
        email_arg = args[1] if len(args) > 1 and "@" in args[1] else None

        if subcommand == "email":
            if not email_arg:
                await update.message.reply_text("Please provide your email address:\n`/connect email you@example.com`", parse_mode="Markdown")
                return
            from bot.imap_providers import get_provider_settings, get_app_password_instructions
            ctx.user_data["connect_email"] = email_arg
            settings = get_provider_settings(email_arg)
            instructions = get_app_password_instructions(email_arg)
            if settings:
                ctx.user_data["connect_imap_settings"] = settings
                await update.message.reply_text(instructions, parse_mode="Markdown")
                ctx.user_data["connect_step"] = "email_password"
            else:
                await update.message.reply_text(
                    f"Got it — {email_arg}\n\nWhat's your IMAP server? (e.g. `imap.yourprovider.com`)",
                    parse_mode="Markdown"
                )
                ctx.user_data["connect_step"] = "email_imap_host"

        elif subcommand == "caldav":
            if not email_arg:
                await update.message.reply_text("Please provide your email address:\n`/connect caldav you@example.com`", parse_mode="Markdown")
                return
            ctx.user_data["caldav_username"] = email_arg
            domain = email_arg.split("@")[-1].lower()
            DOMAIN_PROVIDER = {
                "gmail.com": "google", "googlemail.com": "google",
                "icloud.com": "icloud", "me.com": "icloud", "mac.com": "icloud",
                "fastmail.com": "fastmail", "fastmail.fm": "fastmail",
                "outlook.com": "outlook", "hotmail.com": "outlook",
                "live.com": "outlook", "msn.com": "outlook",
            }
            provider = DOMAIN_PROVIDER.get(domain)
            if provider:
                # Inject as if the user typed the provider and let the existing step handle it
                ctx.user_data["connect_step"] = "caldav_provider"
                # Simulate by directly processing the provider
                fake_update_text = provider
                ctx.user_data["_caldav_auto_provider"] = provider
            else:
                ctx.user_data["_caldav_auto_provider"] = None
            if provider:
                await update.message.reply_text(
                    f"Detected *{provider.capitalize()}* from your email domain. Setting up…",
                    parse_mode="Markdown"
                )
                # Fall through to caldav_provider handling below by setting step and re-entering flow
                ctx.user_data["connect_step"] = "caldav_provider"
                # Directly process the provider without waiting for user input
                CALDAV_URLS_LOCAL = {
                    "icloud": "https://caldav.icloud.com",
                    "fastmail": "https://caldav.fastmail.com",
                    "outlook": None,
                    "google": None,
                }
                CALDAV_HINTS_LOCAL = {
                    "icloud": "Use an *app-specific password* — not your Apple ID password.\n[Generate app password](https://appleid.apple.com/account/manage/section/security)",
                    "fastmail": "Use a Fastmail app password.\n[Generate app password](https://app.fastmail.com/settings/security/tokens/new)",
                    "outlook": "Use your Microsoft account password.\n[Sign in to Outlook](https://outlook.live.com)\n_(Corporate SSO accounts may not work — contact your IT admin)_",
                    "google": "Use a Google *app password* — not your main Google password.\n[Generate app password](https://myaccount.google.com/apppasswords)\n_(Requires 2-Step Verification to be enabled)_",
                }
                ctx.user_data["caldav_url"] = CALDAV_URLS_LOCAL[provider] or "__build__"
                ctx.user_data["caldav_provider"] = provider
                ctx.user_data["caldav_hint"] = CALDAV_HINTS_LOCAL[provider]
                if ctx.user_data["caldav_url"] == "__build__":
                    if provider == "google":
                        ctx.user_data["caldav_url"] = f"https://www.google.com/calendar/dav/{email_arg}/events"
                    else:
                        ctx.user_data["caldav_url"] = f"https://outlook.office365.com/caldav/v1/{email_arg}/Calendar"
                hint = ctx.user_data["caldav_hint"]
                msg = f"Password for {email_arg}:\n\n{hint}"
                await update.message.reply_text(msg, parse_mode="Markdown")
                ctx.user_data["connect_step"] = "caldav_password"
            else:
                await update.message.reply_text(
                    "Which calendar provider do you use?\n\n"
                    "🍎 *iCloud* — type: `icloud`\n"
                    "📧 *Fastmail* — type: `fastmail`\n"
                    "🏢 *Outlook* — type: `outlook`\n"
                    "🌐 *Google* — type: `google`\n"
                    "🌐 *Other* — paste your CalDAV server URL",
                    parse_mode="Markdown"
                )
                ctx.user_data["connect_step"] = "caldav_provider"

        elif subcommand == "calendar":
            await update.message.reply_text(
                "Let's connect your calendar. Which provider do you use?\n\n"
                "1 — Google Calendar\n"
                "2 — Outlook / Microsoft\n"
                "3 — Apple iCloud\n"
                "4 — Other (I'll paste the ICS URL directly)"
            )
            ctx.user_data["connect_step"] = "calendar_provider"

        else:
            lines = ["What would you like to connect?\n"]
            lines.append("/connect email you@example.com — Email (Gmail, Outlook, any IMAP)")
            lines.append("/connect caldav you@example.com — Calendar read/write (iCloud, Fastmail, Outlook, Google…)")
            lines.append("/connect calendar — Calendar read-only (ICS URL)")
            await update.message.reply_text("\n".join(lines))

    async def _handle_connect_flow(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
        """Handle multi-step /connect conversations. Returns True if message was consumed."""
        step = ctx.user_data.get("connect_step")
        if not step:
            return False

        uid = update.effective_user.id
        text = (update.message.text or "").strip()

        if text.lower() in ("cancel", "stop", "/cancel", "/stop"):
            ctx.user_data.clear()
            await update.message.reply_text("Cancelled.")
            return True

        # ── Email flow ────────────────────────────────────────────────────────
        if step == "email_address":
            if "@" not in text:
                await update.message.reply_text("That doesn't look like an email address. Please try again.")
                return True
            ctx.user_data["connect_email"] = text
            from bot.imap_providers import get_provider_settings, get_app_password_instructions
            settings = get_provider_settings(text)
            instructions = get_app_password_instructions(text)
            if settings:
                ctx.user_data["connect_imap_settings"] = settings
                await update.message.reply_text(instructions, parse_mode="Markdown")
                ctx.user_data["connect_step"] = "email_password"
            else:
                await update.message.reply_text(
                    "I don't recognise this email provider automatically.\n\n"
                    "Please enter your IMAP server (e.g. `imap.yourprovider.com`):",
                    parse_mode="Markdown"
                )
                ctx.user_data["connect_step"] = "email_imap_host"
            return True

        if step == "email_imap_host":
            ctx.user_data["connect_imap_host"] = text
            await update.message.reply_text("IMAP port? (usually `993`)", parse_mode="Markdown")
            ctx.user_data["connect_step"] = "email_imap_port"
            return True

        if step == "email_imap_port":
            try:
                ctx.user_data["connect_imap_port"] = int(text)
            except ValueError:
                await update.message.reply_text("Please enter a number (e.g. 993).")
                return True
            await update.message.reply_text("SMTP server? (e.g. `smtp.yourprovider.com`)", parse_mode="Markdown")
            ctx.user_data["connect_step"] = "email_smtp_host"
            return True

        if step == "email_smtp_host":
            ctx.user_data["connect_smtp_host"] = text
            await update.message.reply_text("SMTP port? (usually `587`)", parse_mode="Markdown")
            ctx.user_data["connect_step"] = "email_smtp_port"
            return True

        if step == "email_smtp_port":
            try:
                ctx.user_data["connect_smtp_port"] = int(text)
            except ValueError:
                await update.message.reply_text("Please enter a number (e.g. 587).")
                return True
            await update.message.reply_text("Now enter your email password (or app password):")
            ctx.user_data["connect_step"] = "email_password"
            return True

        if step == "email_password":
            email_addr = ctx.user_data.get("connect_email", "")
            imap_settings = ctx.user_data.get("connect_imap_settings")
            if imap_settings:
                imap_host, imap_port, smtp_host, smtp_port = imap_settings
            else:
                imap_host = ctx.user_data.get("connect_imap_host", "")
                imap_port = ctx.user_data.get("connect_imap_port", 993)
                smtp_host = ctx.user_data.get("connect_smtp_host", "")
                smtp_port = ctx.user_data.get("connect_smtp_port", 587)

            # Test the connection before saving
            await ctx.bot.send_chat_action(chat_id=uid, action="typing")
            import imaplib, ssl
            try:
                ctx_ssl = ssl.create_default_context()
                with imaplib.IMAP4_SSL(imap_host, imap_port, ssl_context=ctx_ssl) as imap:
                    imap.login(email_addr, text)
            except Exception as e:
                for k in ("connect_step", "connect_email", "connect_imap_settings",
                          "connect_imap_host", "connect_imap_port",
                          "connect_smtp_host", "connect_smtp_port"):
                    ctx.user_data.pop(k, None)
                await update.message.reply_text(
                    f"Could not connect to your email: {e}\n\n"
                    "Please double-check your address and password, then try /connect email again."
                )
                return True

            storage = self._get_storage(uid)
            storage.save_imap_config({
                "email": email_addr,
                "password": text,
                "imap_host": imap_host,
                "imap_port": imap_port,
                "smtp_host": smtp_host,
                "smtp_port": smtp_port,
            })
            for k in ("connect_step", "connect_email", "connect_imap_settings",
                      "connect_imap_host", "connect_imap_port",
                      "connect_smtp_host", "connect_smtp_port"):
                ctx.user_data.pop(k, None)
            await update.message.reply_text(f"✅ Email connected ({email_addr})")
            return True

        # ── Calendar flow ─────────────────────────────────────────────────────
        if step == "calendar_provider":
            CALENDAR_INSTRUCTIONS = {
                "1": (
                    "To get your Google Calendar URL:\n\n"
                    "1. Open Google Calendar (calendar.google.com)\n"
                    "2. Click ⚙️ *Settings* (top right)\n"
                    "3. On the left, click your calendar name\n"
                    "4. Scroll down to *Secret address in iCal format*\n"
                    "5. Copy that URL and paste it here"
                ),
                "2": (
                    "To get your Outlook calendar URL:\n\n"
                    "1. Go to outlook.live.com/calendar\n"
                    "2. Click the ⚙️ gear → *View all Outlook settings*\n"
                    "3. Go to *Calendar* → *Shared calendars*\n"
                    "4. Under *Publish a calendar*, select your calendar and choose *Can view all details*\n"
                    "5. Click *Publish*, then copy the ICS link and paste it here"
                ),
                "3": (
                    "To get your iCloud calendar URL:\n\n"
                    "1. Go to icloud.com/calendar\n"
                    "2. Click the sharing icon (📡) next to your calendar name\n"
                    "3. Check *Public Calendar*\n"
                    "4. Copy the URL shown and paste it here"
                ),
                "4": (
                    "Paste your ICS calendar URL here.\n"
                    "It usually ends in `.ics` or contains `ical` in the address."
                ),
            }
            instructions = CALENDAR_INSTRUCTIONS.get(text)
            if not instructions:
                await update.message.reply_text("Please reply with 1, 2, 3 or 4.")
                return True
            await update.message.reply_text(instructions, parse_mode="Markdown")
            ctx.user_data["connect_step"] = "calendar_url"
            return True

        if step == "calendar_url":
            url = text
            if not url.startswith("http"):
                await update.message.reply_text(
                    "That doesn't look like a URL. Please paste the full calendar link (starting with https://)."
                )
                return True
            # Verify it fetches and parses
            await ctx.bot.send_chat_action(chat_id=uid, action="typing")
            try:
                import httpx as _httpx
                from icalendar import Calendar
                resp = _httpx.get(url, timeout=15, follow_redirects=True)
                resp.raise_for_status()
                Calendar.from_ical(resp.content)
            except Exception as e:
                ctx.user_data.pop("connect_step", None)
                await update.message.reply_text(
                    f"Could not read that calendar URL: {e}\n\n"
                    "Please double-check the URL and try /connect calendar again."
                )
                return True
            storage = self._get_storage(uid)
            storage.save_calendar_config({"ics_url": url})
            ctx.user_data.pop("connect_step", None)
            await update.message.reply_text("✅ Calendar connected (read-only)")
            return True

        # ── CalDAV flow ───────────────────────────────────────────────────────
        CALDAV_URLS = {
            "icloud": "https://caldav.icloud.com",
            "fastmail": "https://caldav.fastmail.com",
            "outlook": None,  # URL built from username
            "google": None,   # URL built from username
        }
        CALDAV_HINTS = {
            "icloud": "Use an *app-specific password* — not your Apple ID password.\nGenerate one at [appleid.apple.com](https://appleid.apple.com) → Sign-In and Security → App-Specific Passwords.",
            "fastmail": "Use your Fastmail password or an app password from Fastmail settings.",
            "outlook": "Use your Microsoft account email and password.\n_(Corporate SSO accounts may not work)_",
            "google": "Use a Google *app password* — not your main Google password.\n[Generate app password](https://myaccount.google.com/apppasswords)\n_(Requires 2-Step Verification to be enabled)_",
        }

        if step == "caldav_provider":
            provider = text.lower().strip()
            if provider in CALDAV_URLS:
                ctx.user_data["caldav_url"] = CALDAV_URLS[provider] or "__build__"
                ctx.user_data["caldav_provider"] = provider
                ctx.user_data["caldav_hint"] = CALDAV_HINTS.get(provider, "")
                # Skip username step if pre-filled
                if ctx.user_data.get("caldav_username"):
                    username = ctx.user_data["caldav_username"]
                    if ctx.user_data["caldav_url"] == "__build__":
                        if provider == "google":
                            ctx.user_data["caldav_url"] = f"https://www.google.com/calendar/dav/{username}/events"
                        else:
                            ctx.user_data["caldav_url"] = f"https://outlook.office365.com/caldav/v1/{username}/Calendar"
                    hint = ctx.user_data["caldav_hint"]
                    msg = f"Got it! Password for {username}:"
                    if hint:
                        msg += f"\n\n{hint}"
                    await update.message.reply_text(msg, parse_mode="Markdown")
                    ctx.user_data["connect_step"] = "caldav_password"
                else:
                    await update.message.reply_text(f"Your email address for {text}:")
                    ctx.user_data["connect_step"] = "caldav_username"
            elif text.startswith("http"):
                ctx.user_data["caldav_url"] = text
                ctx.user_data["caldav_hint"] = ""
                if ctx.user_data.get("caldav_username"):
                    hint = ""
                    await update.message.reply_text(f"Password for {ctx.user_data['caldav_username']}:")
                    ctx.user_data["connect_step"] = "caldav_password"
                else:
                    await update.message.reply_text("Your username (usually your email address):")
                    ctx.user_data["connect_step"] = "caldav_username"
            else:
                await update.message.reply_text(
                    "Please type one of: `icloud`, `fastmail`, `outlook`, `google`, or paste your server URL.",
                    parse_mode="Markdown"
                )
            return True

        if step == "caldav_url":
            if not text.startswith("http"):
                await update.message.reply_text("Please paste a URL starting with https://")
                return True
            ctx.user_data["caldav_url"] = text
            await update.message.reply_text("Your CalDAV username (usually your email address):")
            ctx.user_data["connect_step"] = "caldav_username"
            return True

        if step == "caldav_username":
            ctx.user_data["caldav_username"] = text
            provider = ctx.user_data.get("caldav_provider", "")
            if ctx.user_data.get("caldav_url") == "__build__":
                if provider == "google":
                    ctx.user_data["caldav_url"] = f"https://apidata.googleusercontent.com/caldav/v2/{text}/events"
                else:
                    ctx.user_data["caldav_url"] = f"https://outlook.office365.com/caldav/v1/{text}/Calendar"
            hint = ctx.user_data.get("caldav_hint", "")
            msg = "Your password:"
            if hint:
                msg += f"\n\n{hint}"
            await update.message.reply_text(msg, parse_mode="Markdown")
            ctx.user_data["connect_step"] = "caldav_password"
            return True

        if step == "caldav_password":
            await ctx.bot.send_chat_action(chat_id=uid, action="typing")
            caldav_url = ctx.user_data.get("caldav_url", "")
            username = ctx.user_data.get("caldav_username", "")
            password = text
            try:
                import caldav
                client = caldav.DAVClient(url=caldav_url, username=username, password=password)
                principal = client.principal()
                calendars = principal.calendars()
                if not calendars:
                    raise ValueError("No calendars found.")
                cal_names = [c.name for c in calendars]
            except Exception as e:
                for k in ("connect_step", "caldav_url", "caldav_username", "caldav_hint", "caldav_provider"):
                    ctx.user_data.pop(k, None)
                await update.message.reply_text(
                    f"Could not connect: {e}\n\nPlease check your URL and credentials, then try /connect caldav again."
                )
                return True

            storage = self._get_storage(uid)
            storage.save_caldav_config({
                "caldav_url": caldav_url,
                "username": username,
                "password": password,
                "calendar_name": cal_names[0] if cal_names else None,
            })
            for k in ("connect_step", "caldav_url", "caldav_username"):
                ctx.user_data.pop(k, None)
            names_str = ", ".join(cal_names[:5])
            await update.message.reply_text(
                f"✅ CalDAV connected! Found calendars: {names_str}\n\n"
                "I can now create, update and delete events."
            )
            return True

        return False

    async def message(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        user = self.global_db.get_user(uid)
        if not user or user["status"] != "approved":
            return

        # Multi-step connect flows (email, calendar)
        if await self._handle_connect_flow(update, ctx):
            return

        text = update.message.text or ""
        storage = self._get_storage(uid)
        storage.db.add_message(role="user", content=text)

        # Handle explicit QR generation requests directly (narrowed to avoid false positives
        # like "what is a QR code?" or "show me my previous QR codes")
        _qr_gen = _re.search(
            r"(?:generate|create|make|gen(?:erate)?|сделай|создай|сгенерируй)\s+(?:a\s+)?qr(?:\s+code)?(?:\s+for)?\s+(.+)"
            r"|qr\s+code\s+for\s+(.+)",
            text, _re.IGNORECASE,
        )
        if _qr_gen:
            from bot.tools.qrcode_tool import generate_qr
            qr_text = (_qr_gen.group(1) or _qr_gen.group(2)).strip()
            result = generate_qr(qr_text)
            await _send_reply(update.message, result)
            return

        runner = self._get_runner(storage, telegram_id=uid)

        async def keep_typing(stop_event: asyncio.Event):
            while not stop_event.is_set():
                try:
                    await ctx.bot.send_chat_action(chat_id=uid, action="typing")
                except Exception:
                    pass
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=4)
                except asyncio.TimeoutError:
                    pass

        stop_typing = asyncio.Event()
        typing_task = asyncio.create_task(keep_typing(stop_typing))

        try:
            reply = await runner.run(text)
        except Exception as e:
            logger.exception("Agent error for user %s", uid)
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
        finally:
            stop_typing.set()
            typing_task.cancel()

        storage.append_log(text, reply)
        storage.db.add_message(role="assistant", content=reply)
        await _send_reply(update.message, reply)

    async def voice(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        user = self.global_db.get_user(uid)
        if not user or user["status"] != "approved":
            return

        await update.message.reply_text("Got it, transcribing your voice message...")
        voice_file = await update.message.voice.get_file()
        ogg_bytes = bytes(await voice_file.download_as_bytearray())

        async def keep_typing(stop_event: asyncio.Event):
            while not stop_event.is_set():
                try:
                    await ctx.bot.send_chat_action(chat_id=uid, action="typing")
                except Exception:
                    pass
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=4)
                except asyncio.TimeoutError:
                    pass

        async def process():
            stop_typing = asyncio.Event()
            typing_task = asyncio.create_task(keep_typing(stop_typing))
            try:
                loop = asyncio.get_running_loop()
                transcript = await loop.run_in_executor(None, self._transcribe, ogg_bytes)
                storage = self._get_storage(uid)
                storage.db.add_message(role="user", content=f"[Voice] {transcript}")
                runner = self._get_runner(storage, telegram_id=uid)
                try:
                    reply = await runner.run(transcript)
                except Exception as e:
                    logger.exception("Agent error (voice) for user %s", uid)
                    reply = "Something went wrong processing your voice message."
                    await self._notify_admin_error(ctx, uid, e, "voice")
                storage.append_log(transcript, reply)
                storage.db.add_message(role="assistant", content=reply)
            finally:
                stop_typing.set()
                typing_task.cancel()
            await _send_reply_to_chat(ctx.bot, uid, reply)

        asyncio.create_task(process())

    async def _notify_admin_error(self, ctx: ContextTypes.DEFAULT_TYPE, uid: int, error: Exception, context: str = ""):
        admin = self.global_db.get_admin()
        if admin:
            try:
                msg = f"Error for user {uid}"
                if context:
                    msg += f" ({context})"
                msg += f": {error}"
                await ctx.bot.send_message(chat_id=admin["telegram_id"], text=msg)
            except Exception:
                pass

    def _transcribe(self, ogg_bytes: bytes) -> str:
        import tempfile
        from faster_whisper import WhisperModel
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            f.write(ogg_bytes)
            path = f.name
        try:
            segments, _ = model.transcribe(path)
            return " ".join(s.text for s in segments)
        finally:
            _os.unlink(path)

    async def document(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        user = self.global_db.get_user(uid)
        if not user or user["status"] != "approved":
            return
        doc = update.message.document
        if doc.mime_type != "application/pdf":
            await update.message.reply_text("Send me a PDF and I'll summarize it.")
            return
        await update.message.reply_text("Reading your PDF, I'll send the summary shortly...")
        file = await doc.get_file()
        pdf_bytes = bytes(await file.download_as_bytearray())

        async def process():
            from bot.tools.pdf_tool import extract_pdf_text
            text = extract_pdf_text(pdf_bytes)
            storage = self._get_storage(uid)
            runner = self._get_runner(storage, telegram_id=uid)
            caption = (update.message.caption or "").strip()
            prompt = f"{caption}\n\n{text}" if caption else f"Summarize this document:\n\n{text}"
            try:
                reply = await runner.run(prompt)
            except Exception as e:
                logger.exception("Agent error (PDF) for user %s", uid)
                reply = "Could not summarize the PDF."
                await self._notify_admin_error(ctx, uid, e, "PDF")
            await ctx.bot.send_message(chat_id=uid, text=reply)

        asyncio.create_task(process())
