import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bot.storage import UserStorage, DEFAULT_HEARTBEAT
from bot.tools.heartbeat_tool import build_heartbeat_tools
from bot.heartbeat import HeartbeatRunner, schedule_heartbeat, HEARTBEAT_PROMPT


@pytest.fixture
def storage(tmp_path):
    return UserStorage(data_dir=str(tmp_path), telegram_id=12345)


def test_read_heartbeat_defaults(storage):
    content = storage.read_heartbeat()
    assert "Heartbeat Instructions" in content
    assert content == DEFAULT_HEARTBEAT


def test_write_read_heartbeat(storage):
    storage.write_heartbeat("Check emails daily")
    assert storage.read_heartbeat() == "Check emails daily"


def test_update_heartbeat_tool(storage):
    tools = build_heartbeat_tools(storage)
    update_fn = tools[0]
    result = update_fn("Check weather every morning")
    assert "updated" in result.lower()
    assert storage.read_heartbeat() == "Check weather every morning"


def test_heartbeat_runner_calls_agent(storage):
    import asyncio
    mock_bot = AsyncMock()
    mock_agent_result = "You have a meeting tomorrow at 9am."

    async def mock_run(prompt):
        assert prompt == HEARTBEAT_PROMPT
        return mock_agent_result

    mock_runner = MagicMock()
    mock_runner.run = mock_run

    def mock_tools_factory(s, tid):
        return []

    async def run_test():
        with patch("bot.agent.AgentRunner", return_value=mock_runner):
            runner = HeartbeatRunner(
                telegram_id=12345,
                storage=storage,
                bot=mock_bot,
                tools_factory=mock_tools_factory,
            )
            await runner.run()
        mock_bot.send_message.assert_called_once_with(chat_id=12345, text=mock_agent_result)

    asyncio.run(run_test())


def test_heartbeat_registered_in_scheduler(storage):
    from apscheduler.schedulers.background import BackgroundScheduler
    mock_bot = MagicMock()
    scheduler_mock = MagicMock()
    scheduler_mock.scheduler = BackgroundScheduler()
    scheduler_mock.scheduler.start()

    def mock_tools_factory(s, tid):
        return []

    schedule_heartbeat(scheduler_mock, 12345, storage, mock_bot, mock_tools_factory)

    job_ids = [job.id for job in scheduler_mock.scheduler.get_jobs()]
    assert "heartbeat_12345" in job_ids

    scheduler_mock.scheduler.shutdown(wait=False)


def test_heartbeat_no_message_when_empty_result(storage):
    import asyncio
    mock_bot = AsyncMock()

    async def mock_run_empty(prompt):
        return ""

    mock_runner = MagicMock()
    mock_runner.run = mock_run_empty

    def mock_tools_factory(s, tid):
        return []

    async def run_test():
        with patch("bot.agent.AgentRunner", return_value=mock_runner):
            runner = HeartbeatRunner(
                telegram_id=12345,
                storage=storage,
                bot=mock_bot,
                tools_factory=mock_tools_factory,
            )
            await runner.run()
        mock_bot.send_message.assert_not_called()

    asyncio.run(run_test())


def test_heartbeat_no_message_when_whitespace_result(storage):
    import asyncio
    mock_bot = AsyncMock()

    async def mock_run_whitespace(prompt):
        return "   \n  "

    mock_runner = MagicMock()
    mock_runner.run = mock_run_whitespace

    def mock_tools_factory(s, tid):
        return []

    async def run_test():
        with patch("bot.agent.AgentRunner", return_value=mock_runner):
            runner = HeartbeatRunner(
                telegram_id=12345,
                storage=storage,
                bot=mock_bot,
                tools_factory=mock_tools_factory,
            )
            await runner.run()
        mock_bot.send_message.assert_not_called()

    asyncio.run(run_test())


def test_heartbeat_reschedule_replaces_existing(storage):
    from apscheduler.schedulers.background import BackgroundScheduler
    mock_bot = MagicMock()
    scheduler_mock = MagicMock()
    scheduler_mock.scheduler = BackgroundScheduler()
    scheduler_mock.scheduler.start()

    def mock_tools_factory(s, tid):
        return []

    schedule_heartbeat(scheduler_mock, 12345, storage, mock_bot, mock_tools_factory)
    schedule_heartbeat(scheduler_mock, 12345, storage, mock_bot, mock_tools_factory)  # second call

    job_ids = [job.id for job in scheduler_mock.scheduler.get_jobs()]
    assert job_ids.count("heartbeat_12345") == 1  # replace_existing=True, no duplicates

    scheduler_mock.scheduler.shutdown(wait=False)
