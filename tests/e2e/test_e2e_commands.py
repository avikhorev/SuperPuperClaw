"""Real Telegram E2E tests for bot commands."""
import pytest
from tests.e2e.conftest import e2e, send_and_wait


@e2e
async def test_help_command(tg_client, bot_username):
    reply = await send_and_wait(tg_client, bot_username, "/help")
    assert "/help" in reply or "Commands" in reply or "assistant" in reply.lower()


@e2e
async def test_status_command(tg_client, bot_username):
    reply = await send_and_wait(tg_client, bot_username, "/status")
    assert "Email" in reply or "Calendar" in reply


@e2e
async def test_cancel_command(tg_client, bot_username):
    reply = await send_and_wait(tg_client, bot_username, "/cancel")
    assert "cancel" in reply.lower()


@e2e
async def test_connect_no_args(tg_client, bot_username):
    reply = await send_and_wait(tg_client, bot_username, "/connect")
    assert "email" in reply.lower() or "caldav" in reply.lower() or "connect" in reply.lower()


@e2e
async def test_simple_message_gets_reply(tg_client, bot_username):
    reply = await send_and_wait(tg_client, bot_username, "Hello!")
    assert reply and len(reply.strip()) > 0
