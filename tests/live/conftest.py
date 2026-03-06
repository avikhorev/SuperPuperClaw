import os
import shutil
import subprocess
import pytest
from functools import partial


def _has_api_key() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def _has_claude_cli() -> bool:
    """Return True if the claude CLI is installed and responsive (subscription mode)."""
    if not shutil.which("claude"):
        return False
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def _live_available() -> bool:
    return _has_api_key() or _has_claude_cli()


def _skip_reason() -> str:
    if _has_api_key():
        return ""
    if _has_claude_cli():
        return ""
    return "requires ANTHROPIC_API_KEY or an authenticated claude CLI (run: claude login)"


live = pytest.mark.skipif(
    not _live_available(),
    reason=_skip_reason(),
)


@pytest.fixture(autouse=True)
def unset_claudecode_env(monkeypatch):
    """Prevent 'nested Claude Code session' error when running from inside Claude Code."""
    monkeypatch.delenv("CLAUDECODE", raising=False)


@pytest.fixture
def live_storage(tmp_path):
    from bot.storage import UserStorage
    return UserStorage(data_dir=str(tmp_path), telegram_id=1)


def build_runner(storage):
    from bot.agent import AgentRunner
    from bot.tools.memory_tool import update_profile, update_context
    from bot.tools.skills_tool import build_skills_tools
    from bot.tools.heartbeat_tool import build_heartbeat_tools
    from bot.tools.logs_tool import build_logs_tools

    tools = []
    for fn in (update_profile, update_context):
        bound = partial(fn, storage=storage)
        bound.__name__ = fn.__name__
        bound.__doc__ = fn.__doc__
        bound._needs_storage = False
        tools.append(bound)
    tools += build_skills_tools(storage)
    tools += build_heartbeat_tools(storage)
    tools += build_logs_tools(storage)
    return AgentRunner(storage=storage, tools=tools)


@pytest.fixture
def live_runner(live_storage):
    return build_runner(live_storage)
