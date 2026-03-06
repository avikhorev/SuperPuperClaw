"""
Telegram test-server E2E tests.

Uses Telegram's official test DC — no real phone number or SIM needed.

Setup (one time):
  1. Go to https://my.telegram.org, enable test mode (add ?test=1 to the URL
     or use the dedicated test login page), get API credentials.
  2. Create a bot via @BotFather *on the test server* — start a conversation
     with @BotFather while your client is connected to the test DC.
  3. Run your bot with TELEGRAM_TEST_DC=1 and the test bot token.
  4. Set the env vars below and run once with -s to save the session file.
     Subsequent runs are fully automated.

Required env vars:
  TG_TEST_API_ID        — API ID from https://my.telegram.org (test mode)
  TG_TEST_API_HASH      — API hash from https://my.telegram.org (test mode)
  TG_TEST_PHONE         — Any +99966XXXXXX number (no real SIM needed)
  TG_TEST_BOT_USERNAME  — Username of the bot running on test DC

Phone / code format:
  Phone:  +9996621234   (suffix can be any digits)
  Code:   22222         (last digit × 5 — always works, no SMS)

Run:
  TG_TEST_API_ID=... TG_TEST_API_HASH=... TG_TEST_PHONE=+9996621234 \\
  TG_TEST_BOT_USERNAME=@mytestbot pytest tests/e2e/test_e2e_testserver.py -v -s
"""
import asyncio
import pytest
from tests.e2e.conftest import e2e_testserver, send_and_wait


# ── commands ──────────────────────────────────────────────────────────────────

@e2e_testserver
async def test_ts_help_command(tg_test_client, test_bot_username):
    reply = await send_and_wait(tg_test_client, test_bot_username, "/help")
    assert "/help" in reply or "Commands" in reply or "assistant" in reply.lower()


@e2e_testserver
async def test_ts_status_command(tg_test_client, test_bot_username):
    reply = await send_and_wait(tg_test_client, test_bot_username, "/status")
    assert "Email" in reply or "Calendar" in reply


@e2e_testserver
async def test_ts_cancel_command(tg_test_client, test_bot_username):
    reply = await send_and_wait(tg_test_client, test_bot_username, "/cancel")
    assert "cancel" in reply.lower()


@e2e_testserver
async def test_ts_connect_no_args(tg_test_client, test_bot_username):
    reply = await send_and_wait(tg_test_client, test_bot_username, "/connect")
    assert "email" in reply.lower() or "caldav" in reply.lower() or "connect" in reply.lower()


# ── connect flow state machine ────────────────────────────────────────────────

@e2e_testserver
async def test_ts_connect_email_step(tg_test_client, test_bot_username):
    """Starting email connect with an address moves to password step."""
    reply = await send_and_wait(
        tg_test_client, test_bot_username, "/connect email test@gmail.com"
    )
    assert "password" in reply.lower() or "app" in reply.lower()


@e2e_testserver
async def test_ts_cancel_mid_connect_flow(tg_test_client, test_bot_username):
    """Typing 'cancel' mid-flow resets the state."""
    await send_and_wait(
        tg_test_client, test_bot_username, "/connect email test@gmail.com"
    )
    reply = await send_and_wait(tg_test_client, test_bot_username, "cancel")
    assert "cancel" in reply.lower()


# ── agent behaviour ───────────────────────────────────────────────────────────

@e2e_testserver
async def test_ts_simple_message(tg_test_client, test_bot_username):
    reply = await send_and_wait(tg_test_client, test_bot_username, "Hello!")
    assert reply and len(reply.strip()) > 0


@e2e_testserver
async def test_ts_factual_question(tg_test_client, test_bot_username):
    reply = await send_and_wait(tg_test_client, test_bot_username, "What is 3 + 3?")
    assert "6" in reply


@e2e_testserver
async def test_ts_multi_turn_context(tg_test_client, test_bot_username):
    await send_and_wait(tg_test_client, test_bot_username, "My favourite animal is a capybara.")
    reply = await send_and_wait(tg_test_client, test_bot_username, "What is my favourite animal?")
    assert "capybara" in reply.lower()


# ── memory ────────────────────────────────────────────────────────────────────

@e2e_testserver
async def test_ts_agent_remembers_name(tg_test_client, test_bot_username):
    await send_and_wait(
        tg_test_client, test_bot_username,
        "My name is TestServerUser. Please remember it."
    )
    reply = await send_and_wait(tg_test_client, test_bot_username, "What is my name?")
    assert "testserveruser" in reply.lower()


# ── skills ────────────────────────────────────────────────────────────────────

@e2e_testserver
async def test_ts_skill_save_and_retrieve(tg_test_client, test_bot_username):
    await send_and_wait(
        tg_test_client, test_bot_username,
        "Save a skill called 'ts_skill' with content: this is a test-server skill"
    )
    reply = await send_and_wait(tg_test_client, test_bot_username, "Show me the ts_skill skill.")
    assert "ts_skill" in reply.lower() or "test-server" in reply.lower()


# ── logs ──────────────────────────────────────────────────────────────────────

@e2e_testserver
async def test_ts_log_search(tg_test_client, test_bot_username):
    unique = "tsUnique4827testserver"
    await send_and_wait(tg_test_client, test_bot_username, f"Note: {unique}")
    await asyncio.sleep(2)
    reply = await send_and_wait(
        tg_test_client, test_bot_username, f"Search my logs for '{unique}'"
    )
    assert unique in reply or "found" in reply.lower() or "result" in reply.lower()


# ── tools ─────────────────────────────────────────────────────────────────────

@e2e_testserver
async def test_ts_weather_tool(tg_test_client, test_bot_username):
    reply = await send_and_wait(tg_test_client, test_bot_username, "What's the weather in Paris?")
    assert any(w in reply.lower() for w in ["weather", "temperature", "°", "celsius", "paris", "wind"])


@e2e_testserver
async def test_ts_no_email_graceful(tg_test_client, test_bot_username):
    reply = await send_and_wait(tg_test_client, test_bot_username, "Show me my unread emails.")
    assert reply  # should explain gracefully, not crash


@e2e_testserver
async def test_ts_reminder_set(tg_test_client, test_bot_username):
    reply = await send_and_wait(
        tg_test_client, test_bot_username,
        "Remind me to take a break every day at 3pm."
    )
    assert reply  # bot should confirm or acknowledge
