#!/usr/bin/env python3
"""
Automated setup for Telegram test-server E2E tests.

Run this once to:
  1. Create a test-server Telegram account (no real SIM needed)
  2. Create a test bot via @BotFather on the test DC
  3. Write a .env.testserver file with all required vars
  4. Start the bot against the test DC and run the tests

Prerequisites (one-time manual step):
  1. Open https://my.telegram.org/?test=1 in a browser
  2. Log in with your real phone number (just to access the dev console)
  3. Go to API Development Tools → create an application
  4. Copy the api_id and api_hash shown there
  5. Pass them as TG_TEST_API_ID and TG_TEST_API_HASH below

Usage:
    TG_TEST_API_ID=12345 TG_TEST_API_HASH=abc123 python scripts/setup_test_telegram.py

After this script completes, run the tests with:
    source .env.testserver
    pytest tests/e2e/test_e2e_testserver.py -v
"""
import asyncio
import os
import re
import subprocess
import sys
import time

# ── config ────────────────────────────────────────────────────────────────────

API_ID   = int(os.environ.get("TG_TEST_API_ID", "") or sys.exit(
    "ERROR: TG_TEST_API_ID not set.\n"
    "Get it from https://my.telegram.org/?test=1 → API Development Tools"
))
API_HASH = os.environ.get("TG_TEST_API_HASH", "") or sys.exit(
    "ERROR: TG_TEST_API_HASH not set.\n"
    "Get it from https://my.telegram.org/?test=1 → API Development Tools"
)

# Test DC connection details
TEST_DC_ID   = 2
TEST_DC_IP   = "149.154.167.40"
TEST_DC_PORT = 443

# Phone for the test user account. Must use +99966XXXXXX format.
# The verification code is always the last digit repeated 5 times.
# e.g. phone +9996632100 → code 00000
TEST_PHONE      = os.environ.get("TG_TEST_PHONE", "+9996632100")
TEST_CODE       = TEST_PHONE.strip()[-1] * 5
SESSION_PATH    = os.environ.get("TG_TEST_SESSION", "/tmp/tg_testserver.session")
BOT_SESSION     = "/tmp/tg_test_bot.session"
ENV_OUT         = ".env.testserver"

BOT_NAME        = "AAAIntegrationTestBot"
BOT_USERNAME    = "aaa_integration_test_bot"  # BotFather may add a suffix if taken


# ── helpers ───────────────────────────────────────────────────────────────────

async def get_botfather_reply(client, after_send: str, wait: float = 4.0) -> str:
    from telethon import TelegramClient
    await client.send_message("botfather", after_send)
    await asyncio.sleep(wait)
    msgs = await client.get_messages("botfather", limit=1)
    return msgs[0].text if msgs else ""


# ── main setup ────────────────────────────────────────────────────────────────

async def setup():
    from telethon import TelegramClient

    print(f"[1/5] Connecting to Telegram test DC ({TEST_DC_IP}:{TEST_DC_PORT})...")
    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    client.session.set_dc(TEST_DC_ID, TEST_DC_IP, TEST_DC_PORT)

    print(f"[2/5] Signing in as {TEST_PHONE} (code={TEST_CODE})...")
    await client.start(
        phone=TEST_PHONE,
        code_callback=lambda: TEST_CODE,
        first_name="TestUser",
        last_name="AAA",
        password=None,
    )
    me = await client.get_me()
    print(f"      Signed in: {me.first_name} {me.last_name} (id={me.id})")

    print("[3/5] Creating a bot via @BotFather...")
    # Start fresh
    reply = await get_botfather_reply(client, "/cancel")
    reply = await get_botfather_reply(client, "/newbot")
    print(f"      BotFather: {reply[:120]}")

    if "Alright" not in reply and "name" not in reply.lower():
        print("      Unexpected BotFather response — trying /start first")
        await get_botfather_reply(client, "/start", wait=2)
        reply = await get_botfather_reply(client, "/newbot")

    reply = await get_botfather_reply(client, BOT_NAME)
    print(f"      BotFather: {reply[:120]}")

    reply = await get_botfather_reply(client, BOT_USERNAME)
    print(f"      BotFather: {reply[:300]}")

    # Extract token from reply
    token_match = re.search(r"(\d+:[A-Za-z0-9_-]{35,})", reply)
    if not token_match:
        print("\nERROR: Could not find bot token in BotFather reply.")
        print("Full reply:", reply)
        print("\nThe username may already be taken. Edit BOT_USERNAME in this script and retry.")
        await client.disconnect()
        sys.exit(1)

    bot_token = token_match.group(1)
    # Username might differ from what we requested — extract it
    username_match = re.search(r"@(\w+)", reply)
    actual_username = "@" + username_match.group(1) if username_match else "@" + BOT_USERNAME
    print(f"      Bot created: {actual_username}  token={bot_token[:20]}...")

    await client.disconnect()

    print(f"[4/5] Writing {ENV_OUT}...")
    env_content = f"""# Telegram test-server E2E environment
# Source this file before running tests:
#   source {ENV_OUT}
#   pytest tests/e2e/test_e2e_testserver.py -v

export TG_TEST_API_ID={API_ID}
export TG_TEST_API_HASH={API_HASH}
export TG_TEST_PHONE={TEST_PHONE}
export TG_TEST_BOT_USERNAME={actual_username}
export TG_TEST_SESSION={SESSION_PATH}

# For running the bot on test DC:
export TELEGRAM_TOKEN={bot_token}
export TELEGRAM_TEST_DC=1
"""
    with open(ENV_OUT, "w") as f:
        f.write(env_content)
    print(f"      Written to {ENV_OUT}")

    print("[5/5] Done.\n")
    print("Next steps:")
    print(f"  1. Start the bot:  source {ENV_OUT} && python -m bot.main")
    print(f"  2. Approve the test account in the bot (send /start from {TEST_PHONE})")
    print(f"  3. Run the tests:  source {ENV_OUT} && pytest tests/e2e/test_e2e_testserver.py -v")


if __name__ == "__main__":
    asyncio.run(setup())
