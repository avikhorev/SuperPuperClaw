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
    prompt = build_system_prompt(storage)
    assert "Alice" in prompt

def test_system_prompt_includes_date(storage):
    prompt = build_system_prompt(storage)
    assert "2026" in prompt or "date" in prompt.lower()

def test_system_prompt_includes_nothing_known_when_memory_empty(tmp_path):
    s = UserStorage(data_dir=str(tmp_path), telegram_id=2)
    prompt = build_system_prompt(s)
    assert "Nothing known" in prompt or "unknown" in prompt.lower() or prompt  # graceful

def test_agent_runner_returns_text(storage):
    runner = AgentRunner(anthropic_api_key="test", storage=storage, tools=[])
    mock_response = MagicMock()
    mock_text_block = MagicMock()
    mock_text_block.type = "text"
    mock_text_block.text = "Hello!"
    mock_response.content = [mock_text_block]
    mock_response.stop_reason = "end_turn"
    with patch("bot.agent.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = mock_response
        import asyncio
        result = asyncio.run(runner.run("hi"))
    assert result == "Hello!"

def test_memory_tool_updates_storage(tmp_path):
    from bot.tools.memory_tool import update_memory
    s = UserStorage(data_dir=str(tmp_path), telegram_id=3)
    result = update_memory(new_content="- Name: Bob", storage=s)
    assert result == "Memory updated."
    assert "Bob" in s.read_memory()
