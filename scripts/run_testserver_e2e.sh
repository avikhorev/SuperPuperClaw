#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Full automated test-server E2E runner.
#
# Usage:
#   TG_TEST_API_ID=12345 TG_TEST_API_HASH=abc123 bash scripts/run_testserver_e2e.sh
#
# What it does:
#   1. Runs setup_test_telegram.py  → creates account + bot, writes .env.testserver
#   2. Sources .env.testserver
#   3. Starts the bot in the background (test DC mode)
#   4. Waits for the bot to be ready
#   5. Runs pytest tests/e2e/test_e2e_testserver.py
#   6. Stops the bot
#
# Prerequisites:
#   - TG_TEST_API_ID and TG_TEST_API_HASH must be set (from my.telegram.org test mode)
#   - pip install telethon  (already done if you ran setup)
# ─────────────────────────────────────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# ── 1. setup ──────────────────────────────────────────────────────────────────
echo "=== Step 1: Setting up test-server account and bot ==="
python scripts/setup_test_telegram.py

# ── 2. load env ───────────────────────────────────────────────────────────────
echo "=== Step 2: Loading .env.testserver ==="
set -a; source .env.testserver; set +a
echo "Bot username: $TG_TEST_BOT_USERNAME"
echo "Bot token:    ${TELEGRAM_TOKEN:0:20}..."

# ── 3. start bot ──────────────────────────────────────────────────────────────
echo "=== Step 3: Starting bot on test DC ==="
DATA_DIR="/tmp/aaa_testserver_data" python -m bot.main &
BOT_PID=$!
echo "Bot PID: $BOT_PID"

# ── 4. wait for bot to be ready ───────────────────────────────────────────────
echo "=== Step 4: Waiting for bot to be ready (10s) ==="
sleep 10

# ── 5. approve test user (send /start and approve via bot itself) ─────────────
echo "=== Step 5: Approving test user via setup script ==="
python - <<'PYEOF'
import asyncio, os
from telethon import TelegramClient

async def approve():
    api_id   = int(os.environ["TG_TEST_API_ID"])
    api_hash = os.environ["TG_TEST_API_HASH"]
    phone    = os.environ["TG_TEST_PHONE"]
    session  = os.environ.get("TG_TEST_SESSION", "/tmp/tg_testserver.session")
    bot_user = os.environ["TG_TEST_BOT_USERNAME"]

    client = TelegramClient(session, api_id, api_hash)
    client.session.set_dc(2, "149.154.167.40", 443)
    last_digit = phone.strip()[-1]
    await client.start(phone=phone, code_callback=lambda: last_digit * 5)

    me = await client.get_me()
    print(f"Connected as {me.first_name} (id={me.id})")

    # Send /start to trigger registration
    await client.send_message(bot_user, "/start")
    await asyncio.sleep(3)
    msgs = await client.get_messages(bot_user, limit=1)
    print("Bot reply:", msgs[0].text[:200] if msgs else "(no reply)")

    # The bot sends an approval request to the admin (which is the bot owner).
    # Since this is a fresh test DC setup, the first user to /start becomes admin.
    # We'll re-/start once more to be sure.
    await asyncio.sleep(2)
    await client.disconnect()

asyncio.run(approve())
PYEOF

# ── 6. run tests ──────────────────────────────────────────────────────────────
echo "=== Step 6: Running test-server E2E tests ==="
python -m pytest tests/e2e/test_e2e_testserver.py -v
TEST_EXIT=$?

# ── 7. stop bot ───────────────────────────────────────────────────────────────
echo "=== Step 7: Stopping bot (PID $BOT_PID) ==="
kill $BOT_PID 2>/dev/null || true
wait $BOT_PID 2>/dev/null || true

echo ""
if [ $TEST_EXIT -eq 0 ]; then
    echo "✅  All test-server E2E tests passed."
else
    echo "❌  Some tests failed (exit $TEST_EXIT)."
fi

exit $TEST_EXIT
