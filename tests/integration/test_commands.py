"""Integration tests for bot commands — no real Claude API calls."""
import pytest
from unittest.mock import patch, AsyncMock
from tests.integration.conftest import ADMIN_ID, USER_ID, make_update, make_ctx
from tests.integration.fakes import FakeUpdate, FakeContext


# ── /start ────────────────────────────────────────────────────────────────────

async def test_start_first_user_becomes_admin(handler, global_db):
    update = make_update(user_id=ADMIN_ID)
    ctx = make_ctx()
    await handler.start(update, ctx)
    assert global_db.get_user(ADMIN_ID)["is_admin"] == 1
    assert any("admin" in r.lower() or "ready" in r.lower() for r in update.message.replies)


async def test_start_second_user_gets_pending_message(handler, global_db):
    global_db.register_user(999, "stranger")
    update = make_update(user_id=999)
    ctx = make_ctx()
    await handler.start(update, ctx)
    assert any("approval" in r.lower() or "request" in r.lower() or "access" in r.lower()
               for r in update.message.replies)


# ── /help ─────────────────────────────────────────────────────────────────────

async def test_help_requires_approved_user(handler):
    # unapproved user — no reply
    uid = 555
    update = make_update(user_id=uid)
    ctx = make_ctx()
    await handler.help_command(update, ctx)
    assert update.message.replies == []


async def test_help_returns_text_for_approved_user(handler, approved_user):
    update = make_update(user_id=USER_ID)
    ctx = make_ctx()
    await handler.help_command(update, ctx)
    assert len(update.message.replies) == 1
    text = update.message.replies[0]
    assert "/help" in text
    assert "/connect" in text


# ── /approve and /ban ─────────────────────────────────────────────────────────

async def test_approve_command(handler, global_db):
    global_db.register_user(USER_ID, "alice")
    update = make_update(user_id=ADMIN_ID)
    ctx = make_ctx()
    ctx.args = [str(USER_ID)]
    await handler.approve_command(update, ctx)
    assert global_db.get_user(USER_ID)["status"] == "approved"
    assert any("approved" in r.lower() for r in update.message.replies)


async def test_approve_command_non_admin_ignored(handler, global_db, approved_user):
    uid2 = 300
    global_db.register_user(uid2, "bob")
    update = make_update(user_id=USER_ID)  # approved but not admin
    ctx = make_ctx()
    ctx.args = [str(uid2)]
    await handler.approve_command(update, ctx)
    assert global_db.get_user(uid2)["status"] != "approved"


async def test_ban_command(handler, global_db):
    global_db.register_user(USER_ID, "alice")
    update = make_update(user_id=ADMIN_ID)
    ctx = make_ctx()
    ctx.args = [str(USER_ID)]
    await handler.ban_command(update, ctx)
    assert global_db.get_user(USER_ID)["status"] == "banned"


# ── /cancel ───────────────────────────────────────────────────────────────────

async def test_cancel_clears_connect_state(handler, approved_user):
    update = make_update(user_id=USER_ID)
    ctx = make_ctx()
    ctx.user_data["connect_step"] = "email_password"
    ctx.user_data["connect_email"] = "alice@example.com"
    await handler.cancel_command(update, ctx)
    assert ctx.user_data == {}
    assert any("cancel" in r.lower() for r in update.message.replies)


# ── /status ───────────────────────────────────────────────────────────────────

async def test_status_shows_not_connected(handler, approved_user):
    update = make_update(user_id=USER_ID)
    ctx = make_ctx()
    await handler.status_command(update, ctx)
    text = update.message.replies[0]
    assert "Email" in text
    assert "Calendar" in text


async def test_status_requires_approved_user(handler):
    uid = 999
    update = make_update(user_id=uid)
    ctx = make_ctx()
    await handler.status_command(update, ctx)
    assert update.message.replies == []


# ── message routing ───────────────────────────────────────────────────────────

async def test_message_ignored_for_unapproved_user(handler):
    uid = 777
    update = make_update("hello", user_id=uid)
    ctx = make_ctx()
    await handler.message(update, ctx)
    assert update.message.replies == []


async def test_message_calls_agent_and_replies(handler, approved_user):
    update = make_update("hello", user_id=USER_ID)
    ctx = make_ctx()
    with patch("bot.handler.AgentRunner.run", new=AsyncMock(return_value="Hi there!")):
        await handler.message(update, ctx)
    assert update.message.replies == ["Hi there!"]


async def test_message_appends_to_log(handler, approved_user, config):
    from bot.storage import UserStorage
    import os
    update = make_update("test message", user_id=USER_ID)
    ctx = make_ctx()
    with patch("bot.handler.AgentRunner.run", new=AsyncMock(return_value="test reply")):
        await handler.message(update, ctx)
    storage = UserStorage(data_dir=config.data_dir, telegram_id=USER_ID)
    logs_dir = os.path.join(storage.user_dir, "logs")
    assert os.path.exists(logs_dir)
    files = os.listdir(logs_dir)
    assert len(files) == 1


async def test_message_saves_to_db(handler, approved_user, config):
    from bot.storage import UserStorage
    update = make_update("hello world", user_id=USER_ID)
    ctx = make_ctx()
    with patch("bot.handler.AgentRunner.run", new=AsyncMock(return_value="reply")):
        await handler.message(update, ctx)
    storage = UserStorage(data_dir=config.data_dir, telegram_id=USER_ID)
    msgs = storage.db.get_recent_messages(10)
    roles = [m["role"] for m in msgs]
    assert "user" in roles
    assert "assistant" in roles
