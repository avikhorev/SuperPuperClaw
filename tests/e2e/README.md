# Real Telegram E2E Tests

Two modes — pick whichever fits your setup.

---

## Option A — Production Telegram account

Uses a real (or spare) Telegram account against the live Telegram network.

### Required env vars

| Variable | Description |
|---|---|
| `TELEGRAM_API_ID` | From https://my.telegram.org |
| `TELEGRAM_API_HASH` | From https://my.telegram.org |
| `TELEGRAM_PHONE` | Account phone, e.g. `+12025551234` |
| `BOT_USERNAME` | Bot username, e.g. `@my_personal_bot` |
| `TELEGRAM_SESSION` | (Optional) Path to `.session` file |

### Run

```bash
TELEGRAM_API_ID=123 TELEGRAM_API_HASH=abc \
TELEGRAM_PHONE=+12025551234 BOT_USERNAME=@mybot \
pytest tests/e2e/test_e2e_commands.py tests/e2e/test_e2e_agent.py -v -s
```

First run prompts for an SMS verification code. Subsequent runs reuse the
saved session file.

---

## Option B — Free Telegram test-server account (no real SIM needed)

Uses Telegram's **official test DC** — a separate network for developers.
Any phone number in `+99966XXXXXX` format is accepted without a real SIM.
The verification code is always the last digit of the phone repeated 5 times,
so the entire flow is fully automated.

### One-time setup

1. **Get test-mode API credentials**
   Go to https://my.telegram.org, append `?test=1` to the URL (or navigate
   to the test login page), log in, and create an application.
   This gives you a separate `api_id` / `api_hash` for the test network.

2. **Create a test bot**
   Connect a Telethon client to the test DC (see below) and start a
   conversation with `@BotFather` — BotFather exists on both networks.
   Create a new bot and copy the token.

3. **Run your bot against test DC**
   Start the bot with `TELEGRAM_TEST_DC=1` set (handled in `bot/main.py`)
   and the test bot token as `TELEGRAM_TOKEN`.

4. **Approve the test account**
   Send `/start` to the bot as the test user, then approve via the admin
   account (`/approve <id>`).

### Phone / code format

```
Phone:  +9996621234   (suffix is arbitrary)
Code:   22222         (last digit × 5 — always, no SMS)
```

### Required env vars

| Variable | Description |
|---|---|
| `TG_TEST_API_ID` | API ID from https://my.telegram.org (test mode) |
| `TG_TEST_API_HASH` | API hash from https://my.telegram.org (test mode) |
| `TG_TEST_PHONE` | A `+99966XXXXXX` number |
| `TG_TEST_BOT_USERNAME` | Username of bot running on test DC |
| `TG_TEST_SESSION` | (Optional) Path to `.session` file |

### Run

```bash
TG_TEST_API_ID=123 TG_TEST_API_HASH=abc \
TG_TEST_PHONE=+9996621234 TG_TEST_BOT_USERNAME=@mytestbot \
pytest tests/e2e/test_e2e_testserver.py -v -s
```

First run saves the session file (no code prompt needed — it's derived
automatically from the phone number). All subsequent runs are fully
non-interactive.

---

## Full-stack tests (no Telegram account needed)

`test_e2e_full_stack.py` uses fake Telegram objects with the real Claude API.
No Telegram account required — only Claude auth.

```bash
pytest tests/e2e/test_e2e_full_stack.py -v
```

---

## Notes

- All test files are **skipped automatically** when the required env vars are not set
- Do not run Telegram tests in parallel — rate limits apply
- Each test takes 5–60 seconds waiting for bot replies
- `pip install telethon` required for Options A and B
