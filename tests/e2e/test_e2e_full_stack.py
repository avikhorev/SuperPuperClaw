"""
Full-stack E2E tests: fake Telegram transport + real Claude + real BotHandler.

No Telegram account needed. These tests are opt-in and skipped unless both:
  1. `RUN_FULLSTACK_E2E=1` is set
  2. Claude is available (ANTHROPIC_API_KEY or authenticated claude CLI)

These tests exercise the entire request path:
  FakeUpdate → BotHandler → AgentRunner → Claude API → tools → storage
"""
import os
import shutil
import subprocess
import pytest

from bot.config import Config
from bot.db import GlobalDB
from bot.storage import UserStorage
from bot.handler import BotHandler
from tests.integration.fakes import FakeUpdate, FakeContext, FakeScheduler


# ── auth detection (same logic as tests/live/conftest.py) ─────────────────────

def _has_api_key() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def _has_claude_cli() -> bool:
    """Return True only when the Claude CLI is installed and authenticated."""
    if not shutil.which("claude"):
        return False
    try:
        result = subprocess.run(
            ["claude", "auth", "status"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def _live_available() -> bool:
    return _has_api_key() or _has_claude_cli()


def _fullstack_enabled() -> bool:
    return os.getenv("RUN_FULLSTACK_E2E") == "1"


def _skip_reason() -> str:
    if not _fullstack_enabled():
        return "set RUN_FULLSTACK_E2E=1 to enable full-stack E2E tests"
    if _live_available():
        return ""
    return "requires ANTHROPIC_API_KEY or an authenticated claude CLI (run: claude login)"


fullstack = pytest.mark.skipif(
    not (_fullstack_enabled() and _live_available()),
    reason=_skip_reason(),
)

ADMIN_ID = 100
USER_ID = 200


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def unset_claudecode_env(monkeypatch):
    monkeypatch.delenv("CLAUDECODE", raising=False)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "test-token")
    config = Config()
    config.data_dir = str(tmp_path / "data")

    global_db = GlobalDB(str(tmp_path / "global.db"))
    global_db.register_user(ADMIN_ID, "admin")
    global_db.register_user(USER_ID, "alice")
    global_db.approve_user(USER_ID)

    scheduler = FakeScheduler()
    handler = BotHandler(config=config, global_db=global_db, scheduler=scheduler)
    storage = UserStorage(data_dir=config.data_dir, telegram_id=USER_ID)

    return {"handler": handler, "storage": storage, "scheduler": scheduler, "config": config}


async def send(env, text: str) -> str:
    """Send a message through BotHandler and return the reply."""
    update = FakeUpdate(text=text, user_id=USER_ID)
    ctx = FakeContext()
    await env["handler"].message(update, ctx)
    assert update.message.replies, f"No reply for: {text!r}"
    return update.message.replies[-1]


# ── basic agent behaviour ─────────────────────────────────────────────────────

@fullstack
async def test_agent_replies(env):
    reply = await send(env, "Hello!")
    assert isinstance(reply, str) and len(reply.strip()) > 0


@fullstack
async def test_agent_answers_factual_question(env):
    reply = await send(env, "What is 2 + 2?")
    assert "4" in reply


@fullstack
async def test_agent_multi_turn_context(env):
    await send(env, "My favourite colour is indigo.")
    reply = await send(env, "What is my favourite colour?")
    assert "indigo" in reply.lower()


# ── memory tools ─────────────────────────────────────────────────────────────

@fullstack
async def test_agent_saves_name_to_profile(env):
    await send(env, "My name is Diana. Please remember it.")
    assert "Diana" in env["storage"].read_profile()


@fullstack
async def test_agent_saves_project_to_context(env):
    await send(env, "I'm working on a project called Falcon. Keep that in mind.")
    context = env["storage"].read_context()
    assert "falcon" in context.lower() or "Falcon" in context


@fullstack
async def test_profile_injected_into_next_prompt(env):
    env["storage"].write_profile("Name: Eve\nCity: Lisbon")
    reply = await send(env, "Where am I based?")
    assert "lisbon" in reply.lower()


# ── skills ────────────────────────────────────────────────────────────────────

@fullstack
async def test_agent_saves_skill(env):
    await send(env, "Save a skill called 'standup' with: List what I did yesterday, today, and blockers.")
    assert env["storage"].read_skill("standup") is not None


@fullstack
async def test_agent_reads_skill(env):
    env["storage"].write_skill("greet", "Always start with: Good day, how can I help?")
    reply = await send(env, "Use my greet skill.")
    assert reply  # agent should read and apply it


@fullstack
async def test_agent_lists_skills(env):
    env["storage"].write_skill("alpha", "do alpha")
    env["storage"].write_skill("beta", "do beta")
    reply = await send(env, "Use the list_skills tool and tell me what user skills I have saved")
    assert "alpha" in reply.lower() or "beta" in reply.lower()


# ── logs ──────────────────────────────────────────────────────────────────────

@fullstack
async def test_conversation_written_to_log(env):
    await send(env, "Note: the launch is on Thursday.")
    logs_dir = os.path.join(env["storage"].user_dir, "logs")
    assert os.path.exists(logs_dir) and os.listdir(logs_dir)


@fullstack
async def test_agent_searches_logs(env):
    env["storage"].append_log("I need to call the dentist", "Got it, noted.")
    reply = await send(env, "Did I mention anything about a dentist?")
    assert "dentist" in reply.lower()


@fullstack
async def test_log_grows_across_turns(env):
    for i in range(3):
        await send(env, f"Message number {i}")
    import os
    logs_dir = os.path.join(env["storage"].user_dir, "logs")
    content = open(os.path.join(logs_dir, os.listdir(logs_dir)[0])).read()
    assert content.count("**User:**") == 3


# ── heartbeat ─────────────────────────────────────────────────────────────────

@fullstack
async def test_agent_updates_heartbeat(env):
    await send(env, "Set my heartbeat to: check for urgent emails every morning.")
    assert "email" in env["storage"].read_heartbeat().lower()


# ── reminders ─────────────────────────────────────────────────────────────────

@fullstack
async def test_agent_sets_reminder(env):
    await send(env, "Remind me to drink water every day at 8am.")
    jobs = env["storage"].db.list_active_jobs()
    assert len(jobs) >= 1
    descriptions = [j["description"].lower() for j in jobs]
    assert any("water" in d for d in descriptions)


@fullstack
async def test_agent_lists_reminders(env):
    env["storage"].db.add_job("0 8 * * *", "drink water")
    reply = await send(env, "What reminders do I have?")
    assert "water" in reply.lower()


@fullstack
async def test_agent_cancels_reminder(env):
    job_id = env["storage"].db.add_job("0 9 * * 1", "standup call")
    env["scheduler"].add_job(USER_ID, job_id, "0 9 * * 1", "standup call")
    await send(env, f"Cancel reminder {job_id}.")
    jobs = env["storage"].db.list_active_jobs()
    assert all(j["id"] != job_id for j in jobs)


# ── error resilience ──────────────────────────────────────────────────────────

@fullstack
async def test_agent_handles_no_email_configured(env):
    reply = await send(env, "Show me my unread emails.")
    assert reply  # should explain gracefully, not crash


@fullstack
async def test_agent_handles_no_calendar_configured(env):
    reply = await send(env, "What's on my calendar today?")
    assert reply
