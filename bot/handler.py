import asyncio
import logging
import os
from functools import partial

from telegram import Update
from telegram.ext import ContextTypes

from bot.db import GlobalDB
from bot.storage import UserStorage
from bot.agent import AgentRunner
from bot.tools.registry import build_tool_registry
from bot.tools.memory_tool import update_memory

logger = logging.getLogger(__name__)

def _build_help_text(config, storage) -> str:
    has_google_cfg = bool(config.google_client_id)
    has_google = has_google_cfg and storage.load_oauth_tokens() is not None
    has_imap = storage.load_imap_config() is not None
    has_ics = storage.load_calendar_config() is not None
    has_caldav = storage.load_caldav_config() is not None

    lines = ["*Your personal AI assistant*\n"]

    # --- Capabilities ---
    lines.append("*What I can do:*")

    if has_imap:
        lines.append("📧 Email — read, reply, send, delete, mark read")
    if has_google:
        lines.append("📧 Gmail — read, send emails")
        lines.append("📅 Google Calendar — list, create, update, delete events")
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
    lines.append("/status — show connected integrations")
    lines.append("/connect email — link email (IMAP/SMTP)")
    lines.append("/connect caldav — link calendar with write access (iCloud, Fastmail, Nextcloud…)")
    lines.append("/connect calendar — link calendar read-only (ICS URL)")
    if has_google_cfg:
        lines.append("/connect google — link Google account")

    lines.append("\nJust talk to me naturally — no commands needed!")
    return "\n".join(lines)


class BotHandler:
    def __init__(self, config, global_db: GlobalDB):
        self.config = config
        self.global_db = global_db

    def _get_storage(self, telegram_id: int) -> UserStorage:
        return UserStorage(data_dir=self.config.data_dir, telegram_id=telegram_id)

    def _get_runner(self, storage: UserStorage) -> AgentRunner:
        has_google = bool(self.config.google_client_id) and storage.load_oauth_tokens() is not None
        tools = build_tool_registry(storage, has_google=has_google)
        memory_fn = partial(update_memory, storage=storage)
        memory_fn.__name__ = "update_memory"
        memory_fn.__doc__ = update_memory.__doc__
        memory_fn._needs_storage = False  # already bound
        tools.append(memory_fn)
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

    async def status_command(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        user = self.global_db.get_user(uid)
        if not user or user["status"] != "approved":
            return
        lines = []
        if self.config.google_client_id:
            storage = self._get_storage(uid)
            has_google = storage.load_oauth_tokens() is not None
            google_status = "✅ Connected" if has_google else "❌ Not connected — use /connect google"
            lines.append(f"Google: {google_status}")
        else:
            lines.append("Google: not configured by admin")

        storage = self._get_storage(uid)
        imap_cfg = storage.load_imap_config()
        email_status = f"✅ {imap_cfg['email']}" if imap_cfg else "❌ Not connected — use /connect email"
        lines.append(f"Email: {email_status}")

        cal_cfg = storage.load_calendar_config()
        cal_status = "✅ Connected" if cal_cfg else "❌ Not connected — use /connect calendar"
        lines.append(f"Calendar: {cal_status}")

        await update.message.reply_text("\n".join(lines))

    async def connect_command(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        user = self.global_db.get_user(uid)
        if not user or user["status"] != "approved":
            return

        args = ctx.args or []
        subcommand = args[0].lower() if args else ""

        if subcommand == "google":
            if not self.config.google_client_id:
                await update.message.reply_text("Google integration is not configured by the admin.")
                return
            from bot.oauth import OAuthManager
            manager = OAuthManager(self.config.google_client_id, self.config.google_client_secret)
            url = manager.get_auth_url()
            await update.message.reply_text(
                f"Click to authorize Google:\n{url}\n\n"
                "After authorizing, copy the full URL from your browser address bar "
                "(even if it shows an error) and paste it here."
            )
            ctx.user_data["awaiting_oauth"] = True

        elif subcommand == "email":
            await update.message.reply_text(
                "Let's connect your email.\n\nWhat's your email address?"
            )
            ctx.user_data["connect_step"] = "email_address"

        elif subcommand == "caldav":
            await update.message.reply_text(
                "Let's connect your calendar so I can create, edit and delete events.\n\n"
                "Which calendar do you use?\n\n"
                "🍎 *iCloud* — type: `icloud`\n"
                "📧 *Fastmail* — type: `fastmail`\n"
                "🏢 *Outlook / Microsoft 365* — type: `outlook`\n"
                "🌐 *Other* — type your CalDAV server URL directly\n\n"
                "_Note: Google Calendar works better via /connect google_",
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
            if self.config.google_client_id:
                lines.append("/connect google — Gmail, Calendar, Drive (read+write)")
            lines.append("/connect email — Email (any provider)")
            lines.append("/connect caldav — Calendar with write access (iCloud, Fastmail, Nextcloud…)")
            lines.append("/connect calendar — Calendar read-only (any ICS URL)")
            await update.message.reply_text("\n".join(lines))

    async def _handle_connect_flow(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
        """Handle multi-step /connect conversations. Returns True if message was consumed."""
        step = ctx.user_data.get("connect_step")
        if not step:
            return False

        uid = update.effective_user.id
        text = (update.message.text or "").strip()

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
            "outlook": None,  # URL built from username after it's entered
        }

        if step == "caldav_provider":
            provider = text.lower().strip()
            known = CALDAV_URLS.get(provider)
            if provider in CALDAV_URLS:
                if known:
                    ctx.user_data["caldav_url"] = known
                else:
                    ctx.user_data["caldav_url"] = "__build__"  # built after username
                ctx.user_data["caldav_provider"] = provider
                if provider == "icloud":
                    hint = "Use an *app-specific password* — not your Apple ID password.\nGenerate one at [appleid.apple.com](https://appleid.apple.com) → Sign-In and Security → App-Specific Passwords."
                elif provider == "outlook":
                    hint = "Use your Microsoft account email and password.\n_(If your organisation uses SSO/single sign-on, this may not work — contact your IT admin)_"
                else:
                    hint = "Use your Fastmail password or an app password from Fastmail settings."
                await update.message.reply_text(
                    f"Got it! Your email address for {text}:",
                    parse_mode="Markdown"
                )
                ctx.user_data["caldav_hint"] = hint
            elif text.startswith("http"):
                ctx.user_data["caldav_url"] = text
                await update.message.reply_text("Your username (usually your email address):")
                ctx.user_data["caldav_hint"] = ""
            else:
                await update.message.reply_text(
                    "Please type one of: `icloud`, `fastmail`, `outlook`, or paste your server URL.",
                    parse_mode="Markdown"
                )
                return True
            ctx.user_data["connect_step"] = "caldav_username"
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
            if ctx.user_data.get("caldav_url") == "__build__":
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

        # OAuth paste-back flow
        if ctx.user_data.get("awaiting_oauth"):
            ctx.user_data.pop("awaiting_oauth")
            from bot.oauth import OAuthManager, extract_auth_code_from_url
            code = extract_auth_code_from_url(update.message.text or "")
            if not code:
                await update.message.reply_text(
                    "Could not find auth code in that URL. Try /connect google again."
                )
                return
            manager = OAuthManager(self.config.google_client_id, self.config.google_client_secret)
            try:
                tokens = manager.exchange_code(code)
                storage = self._get_storage(uid)
                storage.save_oauth_tokens(tokens)
                await update.message.reply_text(
                    "Google connected! Calendar, Gmail and Drive are now available."
                )
            except Exception as e:
                await update.message.reply_text(f"Authorization failed: {e}")
            return

        # Multi-step connect flows (email, calendar)
        if await self._handle_connect_flow(update, ctx):
            return

        text = update.message.text or ""
        storage = self._get_storage(uid)
        storage.db.add_message(role="user", content=text)
        runner = self._get_runner(storage)

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

        storage.db.add_message(role="assistant", content=reply)
        await update.message.reply_text(reply)

    async def voice(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        user = self.global_db.get_user(uid)
        if not user or user["status"] != "approved":
            return

        await update.message.reply_text("Got it, transcribing your voice message...")
        voice_file = await update.message.voice.get_file()
        ogg_bytes = bytes(await voice_file.download_as_bytearray())

        async def process():
            loop = asyncio.get_running_loop()
            transcript = await loop.run_in_executor(None, self._transcribe, ogg_bytes)
            storage = self._get_storage(uid)
            storage.db.add_message(role="user", content=f"[Voice] {transcript}")
            runner = self._get_runner(storage)
            try:
                reply = await runner.run(transcript)
            except Exception as e:
                logger.exception("Agent error (voice) for user %s", uid)
                reply = "Something went wrong processing your voice message."
                await self._notify_admin_error(ctx, uid, e, "voice")
            storage.db.add_message(role="assistant", content=reply)
            await ctx.bot.send_message(chat_id=uid, text=reply)

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
            os.unlink(path)

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
            runner = self._get_runner(storage)
            try:
                reply = await runner.run(f"Summarize this document:\n\n{text}")
            except Exception as e:
                logger.exception("Agent error (PDF) for user %s", uid)
                reply = "Could not summarize the PDF."
                await self._notify_admin_error(ctx, uid, e, "PDF")
            await ctx.bot.send_message(chat_id=uid, text=reply)

        asyncio.create_task(process())
