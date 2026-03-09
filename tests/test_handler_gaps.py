"""
Tests covering handler gaps that caused real production bugs.

Each test is named after the bug it would have caught.
"""
import asyncio
import os
import tempfile
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── _extract_photos / _send_reply ─────────────────────────────────────────────

from bot.handler import _extract_photos, _send_reply, _send_reply_to_chat


def test_extract_photos_photo_url_token():
    photos, caption = _extract_photos("PHOTO_URL:https://example.com/qr.png")
    assert photos == [("url", "https://example.com/qr.png")]
    assert caption == ""


def test_extract_photos_markdown_image():
    """Bug: Claude converts PHOTO_URL: to markdown ![...](url) before handler sees it."""
    text = "Here's your QR code\n![QR Code](https://api.qrserver.com/v1/create-qr-code/?data=x)"
    photos, caption = _extract_photos(text)
    assert len(photos) == 1
    assert photos[0][0] == "url"
    assert "qrserver.com" in photos[0][1]
    assert "QR Code" in caption or "Here" in caption


def test_extract_photos_plain_text_untouched():
    photos, caption = _extract_photos("Hello world")
    assert photos == []
    assert caption == "Hello world"


def test_extract_photos_photo_file_token(tmp_path):
    p = tmp_path / "test.png"
    p.write_bytes(b"fake")
    photos, caption = _extract_photos(f"PHOTO_FILE:{p}")
    assert photos == [("file", str(p))]
    assert caption == ""


async def test_send_reply_plain_text_sends_reply_text():
    """No photo token → reply_text called, no reply_photo."""
    msg = AsyncMock()
    await _send_reply(msg, "Hello world")
    msg.reply_text.assert_awaited_once_with("Hello world")
    msg.reply_photo.assert_not_awaited()


async def test_send_reply_photo_url_sends_photo_not_text():
    """Bug: used to send caption as separate text message after photo."""
    msg = AsyncMock()
    text = "Here is your QR\n![QR](https://api.qrserver.com/v1/create-qr-code/?data=x)"
    await _send_reply(msg, text)
    msg.reply_photo.assert_awaited_once()
    msg.reply_text.assert_not_awaited()


async def test_send_reply_no_double_message_when_caption_present():
    """Bug: caption was sent both as photo caption AND as separate text message."""
    msg = AsyncMock()
    await _send_reply(msg, "Caption text PHOTO_URL:https://example.com/img.png")
    assert msg.reply_text.await_count == 0
    assert msg.reply_photo.await_count == 1
    _, kwargs = msg.reply_photo.call_args
    assert kwargs.get("caption") == "Caption text"


async def test_send_reply_photo_file_sends_and_deletes(tmp_path):
    path = tmp_path / "qr.png"
    path.write_bytes(b"\x89PNG")
    msg = AsyncMock()
    await _send_reply(msg, f"PHOTO_FILE:{path}")
    msg.reply_photo.assert_awaited_once()
    assert not path.exists()  # file cleaned up


async def test_send_reply_to_chat_photo_url():
    bot = AsyncMock()
    await _send_reply_to_chat(bot, chat_id=42, text="PHOTO_URL:https://example.com/img.png")
    call_kwargs = bot.send_photo.call_args[1]
    assert call_kwargs["chat_id"] == 42
    assert call_kwargs["photo"] == "https://example.com/img.png"
    assert not call_kwargs.get("caption")  # None or empty string
    bot.send_message.assert_not_awaited()


async def test_send_reply_to_chat_plain_text():
    bot = AsyncMock()
    await _send_reply_to_chat(bot, chat_id=42, text="Hello")
    bot.send_message.assert_awaited_once_with(chat_id=42, text="Hello")
    bot.send_photo.assert_not_awaited()


# ── Import smoke test ──────────────────────────────────────────────────────────

def test_all_bot_modules_import():
    """Bug: update_profile ImportError crashed the bot on startup."""
    import bot.main
    import bot.handler
    import bot.agent
    import bot.scheduler
    import bot.heartbeat
    import bot.storage
    import bot.db
    import bot.tools.registry
    import bot.tools.memory_tool
    import bot.tools.heartbeat_tool
    import bot.tools.logs_tool
    import bot.tools.skills_tool
    import bot.tools.reminders
    import bot.tools.youtube
    import bot.tools.qrcode_tool


def test_memory_tool_has_update_profile_and_update_context():
    """Bug: handler imported update_profile/update_context which didn't exist."""
    from bot.tools.memory_tool import update_profile, update_context
    assert callable(update_profile)
    assert callable(update_context)


# ── YouTube error path ─────────────────────────────────────────────────────────

def test_youtube_returns_string_on_failure():
    """Should return a user-friendly string, not raise an exception."""
    from bot.tools.youtube import get_youtube_transcript
    with patch("bot.tools.youtube.YouTubeTranscriptApi") as mock_api:
        mock_api.return_value.list.side_effect = Exception("IP blocked")
        with patch("bot.tools.youtube._transcript_via_ytdlp", side_effect=Exception("blocked")):
            result = get_youtube_transcript("https://www.youtube.com/watch?v=test123")
    assert isinstance(result, str)
    assert len(result) > 0


def test_youtube_invalid_url():
    from bot.tools.youtube import get_youtube_transcript
    result = get_youtube_transcript("https://notvideo.com/page")
    assert "Could not extract" in result


# ── Voice handler: typing animation ───────────────────────────────────────────

async def test_voice_handler_sends_typing_action(tmp_path, monkeypatch):
    """Bug: no typing animation during voice transcription."""
    from bot.config import Config
    from bot.db import GlobalDB
    from bot.handler import BotHandler
    from tests.integration.fakes import FakeScheduler

    monkeypatch.setenv("TELEGRAM_TOKEN", "test-token")
    cfg = Config()
    cfg.data_dir = str(tmp_path / "data")
    db = GlobalDB(str(tmp_path / "global.db"))
    db.register_user(telegram_id=1, username="admin")
    db.approve_user(1)

    handler = BotHandler(config=cfg, global_db=db, scheduler=FakeScheduler())

    typing_calls = []

    update = MagicMock()
    update.effective_user.id = 1
    update.message.voice.get_file = AsyncMock(return_value=AsyncMock(
        download_as_bytearray=AsyncMock(return_value=bytearray(b"fake_ogg"))
    ))
    update.message.reply_text = AsyncMock()

    ctx = MagicMock()
    ctx.bot.send_chat_action = AsyncMock(side_effect=lambda **kw: typing_calls.append(kw))
    ctx.bot.send_message = AsyncMock()

    with patch.object(handler, "_transcribe", return_value="hello"):
        with patch.object(handler, "_get_runner") as mock_runner:
            mock_runner.return_value.run = AsyncMock(return_value="Hi there")
            await handler.voice(update, ctx)
            # Let the background task run
            await asyncio.sleep(0.1)

    assert any(c.get("action") == "typing" for c in typing_calls)


# ── Document handler: caption ──────────────────────────────────────────────────

async def test_document_handler_uses_caption(tmp_path, monkeypatch):
    """Bug: PDF caption was ignored — agent always got 'Summarize this document'."""
    from bot.config import Config
    from bot.db import GlobalDB
    from bot.handler import BotHandler
    from tests.integration.fakes import FakeScheduler

    monkeypatch.setenv("TELEGRAM_TOKEN", "test-token")
    cfg = Config()
    cfg.data_dir = str(tmp_path / "data")
    db = GlobalDB(str(tmp_path / "global.db"))
    db.register_user(telegram_id=1, username="admin")
    db.approve_user(1)

    handler = BotHandler(config=cfg, global_db=db, scheduler=FakeScheduler())
    prompts_received = []

    update = MagicMock()
    update.effective_user.id = 1
    update.message.caption = "extract all prices"
    update.message.document.mime_type = "application/pdf"
    update.message.document.get_file = AsyncMock(return_value=AsyncMock(
        download_as_bytearray=AsyncMock(return_value=bytearray(b"%PDF fake"))
    ))
    update.message.reply_text = AsyncMock()

    ctx = MagicMock()
    ctx.bot.send_message = AsyncMock()

    with patch("bot.tools.pdf_tool.extract_pdf_text", return_value="price: $10"):
        with patch.object(handler, "_get_runner") as mock_runner:
            runner = AsyncMock()
            runner.run = AsyncMock(side_effect=lambda p: prompts_received.append(p) or "done")
            mock_runner.return_value = runner
            await handler.document(update, ctx)
            await asyncio.sleep(0.1)

    assert len(prompts_received) == 1
    assert "extract all prices" in prompts_received[0]


async def test_document_handler_defaults_to_summarize_when_no_caption(tmp_path, monkeypatch):
    """No caption → default summarize prompt."""
    from bot.config import Config
    from bot.db import GlobalDB
    from bot.handler import BotHandler
    from tests.integration.fakes import FakeScheduler

    monkeypatch.setenv("TELEGRAM_TOKEN", "test-token")
    cfg = Config()
    cfg.data_dir = str(tmp_path / "data")
    db = GlobalDB(str(tmp_path / "global.db"))
    db.register_user(telegram_id=1, username="admin")
    db.approve_user(1)

    handler = BotHandler(config=cfg, global_db=db, scheduler=FakeScheduler())
    prompts_received = []

    update = MagicMock()
    update.effective_user.id = 1
    update.message.caption = None
    update.message.document.mime_type = "application/pdf"
    update.message.document.get_file = AsyncMock(return_value=AsyncMock(
        download_as_bytearray=AsyncMock(return_value=bytearray(b"%PDF fake"))
    ))
    update.message.reply_text = AsyncMock()

    ctx = MagicMock()
    ctx.bot.send_message = AsyncMock()

    with patch("bot.tools.pdf_tool.extract_pdf_text", return_value="some text"):
        with patch.object(handler, "_get_runner") as mock_runner:
            runner = AsyncMock()
            runner.run = AsyncMock(side_effect=lambda p: prompts_received.append(p) or "done")
            mock_runner.return_value = runner
            await handler.document(update, ctx)
            await asyncio.sleep(0.1)

    assert len(prompts_received) == 1
    assert "summarize" in prompts_received[0].lower()
