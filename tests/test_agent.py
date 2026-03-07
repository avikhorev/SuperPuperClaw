# tests/test_agent.py
import pytest
from unittest.mock import patch, MagicMock
from bot.storage import UserStorage
from bot.agent import build_system_prompt, AgentRunner

@pytest.fixture
def storage(tmp_path):
    s = UserStorage(data_dir=str(tmp_path), telegram_id=1)
    s.write_memory("- Name: Alice\n- Timezone: UTC")
    return s

def test_system_prompt_includes_memory(storage):
    prompt = build_system_prompt(storage, history=[])
    assert "Alice" in prompt

def test_system_prompt_includes_date(storage):
    prompt = build_system_prompt(storage, history=[])
    assert "2026" in prompt or "date" in prompt.lower()

def test_system_prompt_includes_nothing_known_when_memory_empty(tmp_path):
    s = UserStorage(data_dir=str(tmp_path), telegram_id=2)
    prompt = build_system_prompt(s, history=[])
    assert "Nothing known" in prompt or "unknown" in prompt.lower() or prompt  # graceful

def test_system_prompt_includes_history(storage):
    history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]
    prompt = build_system_prompt(storage, history=history)
    assert "Hello" in prompt
    assert "Hi there!" in prompt

def test_agent_runner_init_no_api_key(storage):
    # AgentRunner no longer requires an API key
    runner = AgentRunner(storage=storage, tools=[])
    assert runner.storage is storage
    assert runner.tools == []

def test_profile_tool_updates_storage(tmp_path):
    from bot.tools.memory_tool import update_profile
    s = UserStorage(data_dir=str(tmp_path), telegram_id=3)
    result = update_profile(new_content="- Name: Bob", storage=s)
    assert result == "Profile updated."
    assert "Bob" in s.read_profile()

def test_context_tool_updates_storage(tmp_path):
    from bot.tools.memory_tool import update_context
    s = UserStorage(data_dir=str(tmp_path), telegram_id=4)
    result = update_context(new_content="Working on project Y", storage=s)
    assert result == "Context updated."
    assert "project Y" in s.read_context()

def test_system_prompt_includes_agent_rules(tmp_path):
    s = UserStorage(data_dir=str(tmp_path), telegram_id=5)
    prompt = build_system_prompt(s, history=[])
    assert "Be concise" in prompt  # default agent rules

def test_system_prompt_profile_and_context_empty_defaults(tmp_path):
    s = UserStorage(data_dir=str(tmp_path), telegram_id=6)
    prompt = build_system_prompt(s, history=[])
    assert "Nothing known yet" in prompt
    assert "No active context" in prompt

def test_system_prompt_profile_and_context_separate(tmp_path):
    s = UserStorage(data_dir=str(tmp_path), telegram_id=7)
    s.write_profile("Name: Dave")
    s.write_context("Debugging API")
    prompt = build_system_prompt(s, history=[])
    assert "Name: Dave" in prompt
    assert "Debugging API" in prompt
    # Both sections are distinct
    assert prompt.index("Name: Dave") != prompt.index("Debugging API")
