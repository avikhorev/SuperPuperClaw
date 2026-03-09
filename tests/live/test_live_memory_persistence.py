"""
Live tests for memory persistence across multiple AgentRunner instances.
Verifies that profile/context survive between 'sessions'.
"""
import pytest
from tests.live.conftest import live
from functools import partial


def make_runner(storage):
    from bot.agent import AgentRunner
    from bot.tools.memory_tool import update_profile, update_context
    from bot.tools.skills_tool import build_skills_tools

    tools = []
    for fn in (update_profile, update_context):
        bound = partial(fn, storage=storage)
        bound.__name__ = fn.__name__
        bound.__doc__ = fn.__doc__
        bound._needs_storage = False
        tools.append(bound)
    tools += build_skills_tools(storage)
    return AgentRunner(storage=storage, tools=tools)


@live
async def test_profile_persists_across_runner_instances(tmp_path):
    from bot.storage import UserStorage
    storage = UserStorage(data_dir=str(tmp_path), telegram_id=1)

    runner1 = make_runner(storage)
    await runner1.run("My name is Charlie and I'm a software engineer.")

    # Create a fresh runner instance, same storage
    runner2 = make_runner(storage)
    reply = await runner2.run("What's my name?")
    assert "Charlie" in reply, f"Profile not persisted: {reply!r}"


@live
async def test_skill_persists_across_runner_instances(tmp_path):
    from bot.storage import UserStorage
    storage = UserStorage(data_dir=str(tmp_path), telegram_id=1)

    runner1 = make_runner(storage)
    await runner1.run("Save a skill called 'greet' with: Always greet the user warmly by name.")

    runner2 = make_runner(storage)
    reply = await runner2.run("Use the greet skill.")
    skill_content = storage.read_skill("greet")
    assert skill_content is not None, "Skill was not saved"
