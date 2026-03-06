"""Integration tests for the /connect multi-step flows."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from tests.integration.conftest import USER_ID, make_update, make_ctx


async def test_connect_no_subcommand_shows_options(handler, approved_user):
    update = make_update(user_id=USER_ID)
    ctx = make_ctx()
    ctx.args = []
    await handler.connect_command(update, ctx)
    text = update.message.replies[0]
    assert "email" in text.lower()
    assert "caldav" in text.lower()


async def test_connect_email_no_address_prompts(handler, approved_user):
    update = make_update(user_id=USER_ID)
    ctx = make_ctx()
    ctx.args = ["email"]
    await handler.connect_command(update, ctx)
    assert any("email" in r.lower() or "address" in r.lower() for r in update.message.replies)


async def test_connect_email_sets_step(handler, approved_user):
    update = make_update(user_id=USER_ID)
    ctx = make_ctx()
    ctx.args = ["email", "alice@gmail.com"]
    await handler.connect_command(update, ctx)
    assert ctx.user_data.get("connect_step") == "email_password"
    assert ctx.user_data.get("connect_email") == "alice@gmail.com"


async def test_connect_email_wrong_password_clears_state(handler, approved_user):
    ctx = make_ctx()
    ctx.user_data["connect_step"] = "email_password"
    ctx.user_data["connect_email"] = "alice@gmail.com"
    ctx.user_data["connect_imap_settings"] = ("imap.gmail.com", 993, "smtp.gmail.com", 587)
    update = make_update("wrongpassword", user_id=USER_ID)
    with patch("imaplib.IMAP4_SSL") as mock_imap:
        mock_imap.return_value.__enter__.return_value.login.side_effect = Exception("auth failed")
        consumed = await handler._handle_connect_flow(update, ctx)
    assert consumed is True
    assert "connect_step" not in ctx.user_data
    assert any("could not" in r.lower() or "failed" in r.lower() or "check" in r.lower()
               for r in update.message.replies)


async def test_connect_email_success_saves_config(handler, approved_user, config):
    from bot.storage import UserStorage
    ctx = make_ctx()
    ctx.user_data["connect_step"] = "email_password"
    ctx.user_data["connect_email"] = "alice@gmail.com"
    ctx.user_data["connect_imap_settings"] = ("imap.gmail.com", 993, "smtp.gmail.com", 587)
    update = make_update("correct_app_password", user_id=USER_ID)
    with patch("imaplib.IMAP4_SSL") as mock_imap:
        mock_imap.return_value.__enter__.return_value.login.return_value = ("OK", [b"Logged in"])
        consumed = await handler._handle_connect_flow(update, ctx)
    assert consumed is True
    storage = UserStorage(data_dir=config.data_dir, telegram_id=USER_ID)
    cfg = storage.load_imap_config()
    assert cfg is not None
    assert cfg["email"] == "alice@gmail.com"
    assert "connect_step" not in ctx.user_data


async def test_cancel_mid_flow(handler, approved_user):
    ctx = make_ctx()
    ctx.user_data["connect_step"] = "email_password"
    update = make_update("cancel", user_id=USER_ID)
    consumed = await handler._handle_connect_flow(update, ctx)
    assert consumed is True
    assert "connect_step" not in ctx.user_data


async def test_connect_caldav_gmail_autodetect(handler, approved_user):
    update = make_update(user_id=USER_ID)
    ctx = make_ctx()
    ctx.args = ["caldav", "alice@gmail.com"]
    await handler.connect_command(update, ctx)
    # Should auto-detect Google and jump to password step
    assert ctx.user_data.get("connect_step") == "caldav_password"
    assert "google.com/calendar/dav" in ctx.user_data.get("caldav_url", "")


async def test_connect_caldav_icloud_autodetect(handler, approved_user):
    update = make_update(user_id=USER_ID)
    ctx = make_ctx()
    ctx.args = ["caldav", "alice@icloud.com"]
    await handler.connect_command(update, ctx)
    assert ctx.user_data.get("connect_step") == "caldav_password"
    assert "icloud.com" in ctx.user_data.get("caldav_url", "")
