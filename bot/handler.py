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

HELP_TEXT = """I'm your personal AI assistant!

📅 *Productivity*
• Google Calendar, Gmail, Drive — type /connect google
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
        memory_fn = partial(update_memory, storage=storage)
        memory_fn.__name__ = "update_memory"
        memory_fn.__doc__ = update_memory.__doc__
        memory_fn._needs_storage = False  # already bound
        tools.append(memory_fn)
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
        storage = self._get_storage(uid)
        has_google = storage.load_oauth_tokens() is not None
        google_status = "✅ Connected" if has_google else "❌ Not connected — use /connect google"
        await update.message.reply_text(f"Google: {google_status}")

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
            "After authorizing, copy the full URL from your browser address bar "
            "(even if it shows an error) and paste it here."
        )
        ctx.user_data["awaiting_oauth"] = True

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

        text = update.message.text or ""
        storage = self._get_storage(uid)
        storage.db.add_message(role="user", content=text)
        await ctx.bot.send_chat_action(chat_id=uid, action="typing")
        runner = self._get_runner(storage)

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
            storage.db.add_message(role="assistant", content=reply)
            await ctx.bot.send_message(chat_id=uid, text=reply)

        asyncio.create_task(process())

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
                reply = "Could not summarize the PDF."
            await ctx.bot.send_message(chat_id=uid, text=reply)

        asyncio.create_task(process())
