"""Live tests for memory persistence across AgentRunner instances.
Runs with ANTHROPIC_API_KEY or an authenticated claude CLI subscription.
"""
import pytest
from tests.live.conftest import live, build_runner


@live
async def test_profile_persists_across_sessions(tmp_path):
    from bot.storage import UserStorage
    storage = UserStorage(data_dir=str(tmp_path), telegram_id=1)

    runner1 = build_runner(storage)
    await runner1.run("My name is Charlie and I'm a software engineer.")

    runner2 = build_runner(storage)
    reply = await runner2.run("What's my name?")
    assert "Charlie" in reply, f"Profile not persisted across sessions: {reply!r}"


@live
async def test_skill_persists_across_sessions(tmp_path):
    from bot.storage import UserStorage
    storage = UserStorage(data_dir=str(tmp_path), telegram_id=1)

    runner1 = build_runner(storage)
    await runner1.run("Save a skill called 'greet' with: Always greet the user warmly by name.")

    runner2 = build_runner(storage)
    skill = storage.read_skill("greet")
    assert skill is not None, "Skill was not saved by first runner"

    reply = await runner2.run("Use the greet skill.")
    assert reply
