"""
Real Telegram E2E test infrastructure using telethon.

Two modes:

Option A — Production Telegram account:
  TELEGRAM_API_ID    — from https://my.telegram.org
  TELEGRAM_API_HASH  — from https://my.telegram.org
  TELEGRAM_PHONE     — e.g. +12025551234
  BOT_USERNAME       — e.g. @my_personal_bot
  TELEGRAM_SESSION   — (optional) session file path

Option B — Free Telegram test-server account (no real SIM needed):
  TG_TEST_API_ID     — from https://my.telegram.org (test mode)
  TG_TEST_API_HASH   — from https://my.telegram.org (test mode)
  TG_TEST_PHONE      — any +99966XXXXXX number (XXXXXX = 6-digit suffix)
  TG_TEST_BOT_USERNAME — username of the bot running on test servers
  TG_TEST_SESSION    — (optional) session file path

  On test servers the verification code is always the last digit of the
  phone repeated 5 times. E.g. +9996621234 → code 22222. No SMS needed.
  The bot must also be connected to test DC (TELEGRAM_TEST_DC=1 env var
  when running the bot).
"""
import os
import asyncio
import pytest

# ── Production Telegram ───────────────────────────────────────────────────────

REQUIRED_VARS = ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_PHONE", "BOT_USERNAME")

e2e = pytest.mark.skipif(
    not all(os.getenv(v) for v in REQUIRED_VARS),
    reason=f"requires env vars: {', '.join(REQUIRED_VARS)}"
)

# ── Test-server Telegram ──────────────────────────────────────────────────────

TEST_SERVER_VARS = (
    "TG_TEST_API_ID", "TG_TEST_API_HASH", "TG_TEST_PHONE", "TG_TEST_BOT_USERNAME"
)

e2e_testserver = pytest.mark.skipif(
    not all(os.getenv(v) for v in TEST_SERVER_VARS),
    reason=f"requires env vars: {', '.join(TEST_SERVER_VARS)}"
)

# Telegram official test DC endpoints
_TEST_DC_ID = 2
_TEST_DC_IP = "149.154.167.40"
_TEST_DC_PORT = 443


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Production client fixture ─────────────────────────────────────────────────

@pytest.fixture(scope="session")
async def tg_client():
    try:
        from telethon import TelegramClient
    except ImportError:
        pytest.skip("telethon not installed — run: pip install telethon")

    api_id = int(os.environ["TELEGRAM_API_ID"])
    api_hash = os.environ["TELEGRAM_API_HASH"]
    phone = os.environ["TELEGRAM_PHONE"]
    session_path = os.getenv("TELEGRAM_SESSION", "/tmp/e2e_test.session")

    client = TelegramClient(session_path, api_id, api_hash)
    await client.start(phone=phone)
    yield client
    await client.disconnect()


@pytest.fixture
def bot_username():
    return os.environ.get("BOT_USERNAME", "")


# ── Test-server client fixture ────────────────────────────────────────────────

@pytest.fixture(scope="session")
async def tg_test_client():
    """
    Telethon client connected to Telegram's official test DC.

    Phone numbers in +99966XXXXXX format are accepted on test servers without
    a real SIM. The verification code is always the last digit × 5.
    E.g. phone +9996621234 → code 22222.

    After the first run the session file is reused, so no code is needed again.
    """
    try:
        from telethon import TelegramClient
    except ImportError:
        pytest.skip("telethon not installed — run: pip install telethon")

    api_id = int(os.environ["TG_TEST_API_ID"])
    api_hash = os.environ["TG_TEST_API_HASH"]
    phone = os.environ["TG_TEST_PHONE"]
    session_path = os.getenv("TG_TEST_SESSION", "/tmp/tg_testserver.session")

    client = TelegramClient(session_path, api_id, api_hash)

    # Route to Telegram test DC before connecting
    client.session.set_dc(_TEST_DC_ID, _TEST_DC_IP, _TEST_DC_PORT)

    # Derive the verification code automatically from the phone number.
    # Telegram test servers always use: last digit repeated 5 times.
    last_digit = phone.strip()[-1]
    auto_code = last_digit * 5

    await client.start(
        phone=phone,
        code_callback=lambda: auto_code,
    )
    yield client
    await client.disconnect()


@pytest.fixture
def test_bot_username():
    return os.environ.get("TG_TEST_BOT_USERNAME", "")


# ── Shared helper ─────────────────────────────────────────────────────────────

async def send_and_wait(client, bot_username: str, text: str, timeout: float = 30.0) -> str:
    """Send a message to the bot and wait for its reply."""
    from telethon import events
    loop = asyncio.get_event_loop()
    reply_future = loop.create_future()

    @client.on(events.NewMessage(from_users=bot_username))
    async def handler(event):
        if not reply_future.done():
            reply_future.set_result(event.message.text)

    try:
        await client.send_message(bot_username, text)
        return await asyncio.wait_for(reply_future, timeout=timeout)
    finally:
        client.remove_event_handler(handler)
