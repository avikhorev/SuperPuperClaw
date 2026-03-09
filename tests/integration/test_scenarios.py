"""Scenario-driven multi-turn conversation tests."""
import os
import pytest
from unittest.mock import patch, AsyncMock
from pathlib import Path

from bot.db import GlobalDB
from bot.storage import UserStorage
from bot.handler import BotHandler
from bot.config import Config
from tests.integration.fakes import FakeUpdate, FakeContext, FakeScheduler
from tests.integration.scenario_runner import ScenarioRunner, load_scenario

USER_ID = 200
ADMIN_ID = 100


@pytest.fixture
def setup(tmp_path, monkeypatch):
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
    return handler, storage, scheduler


async def test_scenario_memory_flow(setup):
    handler, storage, scheduler = setup
    scenario = load_scenario("memory_flow")
    runner = ScenarioRunner(handler, storage, scheduler, USER_ID)
    ctx = FakeContext()
    for turn in scenario["turns"]:
        await runner.run_turn(turn, ctx)
        runner.check_assertions(turn)


async def test_scenario_reminders_flow(setup):
    handler, storage, scheduler = setup
    scenario = load_scenario("reminders_flow")
    runner = ScenarioRunner(handler, storage, scheduler, USER_ID)
    ctx = FakeContext()
    for i, turn in enumerate(scenario["turns"]):
        # Simulate tool side-effect on first turn
        if i == 0:
            storage.db.add_job("0 9 * * 1-5", "standup")
        await runner.run_turn(turn, ctx)
        runner.check_assertions(turn)


async def test_scenario_skills_flow(setup):
    handler, storage, scheduler = setup
    scenario = load_scenario("skills_flow")
    runner = ScenarioRunner(handler, storage, scheduler, USER_ID)
    ctx = FakeContext()
    for i, turn in enumerate(scenario["turns"]):
        if i == 0:
            storage.write_skill("weekly_report", "summarize completed tasks")
        await runner.run_turn(turn, ctx)
        runner.check_assertions(turn)


async def test_scenario_heartbeat_flow(setup):
    handler, storage, scheduler = setup
    scenario = load_scenario("heartbeat_flow")
    runner = ScenarioRunner(handler, storage, scheduler, USER_ID)
    ctx = FakeContext()
    for i, turn in enumerate(scenario["turns"]):
        if i == 0:
            storage.write_heartbeat("check unread emails every morning")
        await runner.run_turn(turn, ctx)
        runner.check_assertions(turn)


async def test_log_grows_across_turns(setup):
    handler, storage, _ = setup
    ctx = FakeContext()
    for i in range(3):
        update = FakeUpdate(text=f"message {i}", user_id=USER_ID)
        with patch("bot.agent.AgentRunner.run", new=AsyncMock(return_value=f"reply {i}")):
            await handler.message(update, ctx)
    logs_dir = os.path.join(storage.user_dir, "logs")
    content = open(os.path.join(logs_dir, os.listdir(logs_dir)[0])).read()
    assert content.count("**User:**") == 3
    assert content.count("**Assistant:**") == 3


async def test_unapproved_user_ignored(setup):
    handler, _, _ = setup
    ctx = FakeContext()
    update = FakeUpdate(text="hello", user_id=999)
    with patch("bot.agent.AgentRunner.run", new=AsyncMock(return_value="should not appear")):
        await handler.message(update, ctx)
    assert update.message.replies == []
