import os
import pytest
import tempfile
from bot.storage import UserStorage, DEFAULT_AGENT_RULES
from bot.tools.memory_tool import update_profile, update_context
from bot.agent import build_system_prompt


@pytest.fixture
def storage(tmp_path):
    return UserStorage(data_dir=str(tmp_path), telegram_id=12345)


def test_profile_read_write(storage):
    assert storage.read_profile() == ""
    storage.write_profile("Name: Alice")
    assert storage.read_profile() == "Name: Alice"


def test_context_read_write(storage):
    assert storage.read_context() == ""
    storage.write_context("Working on project X")
    assert storage.read_context() == "Working on project X"


def test_agent_rules_defaults(storage):
    rules = storage.read_agent_rules()
    assert "Be concise" in rules


def test_update_profile_tool(storage):
    update_profile("Name: Bob", storage)
    profile_path = os.path.join(storage.user_dir, "memory", "profile.md")
    context_path = os.path.join(storage.user_dir, "memory", "context.md")
    assert os.path.exists(profile_path)
    assert not os.path.exists(context_path)
    assert storage.read_profile() == "Name: Bob"


def test_update_context_tool(storage):
    update_context("Working on API integration", storage)
    context_path = os.path.join(storage.user_dir, "memory", "context.md")
    profile_path = os.path.join(storage.user_dir, "memory", "profile.md")
    assert os.path.exists(context_path)
    assert not os.path.exists(profile_path)
    assert storage.read_context() == "Working on API integration"


def test_system_prompt_contains_profile_and_context(storage):
    storage.write_profile("Name: Carol")
    storage.write_context("Building a chatbot")
    prompt = build_system_prompt(storage, [])
    assert "Name: Carol" in prompt
    assert "Building a chatbot" in prompt
