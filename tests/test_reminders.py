"""Tests for reminder tools and scheduler integration."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.db import UserDB
from bot.scheduler import ReminderScheduler, parse_reminder_request
from bot.tools.reminders import build_reminder_tools


# ── UserDB job methods ────────────────────────────────────────────────────────

@pytest.fixture
def user_db(tmp_path):
    return UserDB(str(tmp_path / "conversations.db"))


def test_add_job_returns_id(user_db):
    job_id = user_db.add_job("0 9 * * mon", "standup")
    assert isinstance(job_id, int)
    assert job_id > 0


def test_list_active_jobs(user_db):
    user_db.add_job("0 9 * * mon", "standup")
    user_db.add_job("0 8 * * *", "drink water")
    jobs = user_db.list_active_jobs()
    assert len(jobs) == 2
    assert all(j["active"] == 1 for j in jobs)


def test_cancel_job(user_db):
    job_id = user_db.add_job("0 9 * * mon", "standup")
    user_db.cancel_job(job_id)
    assert user_db.list_active_jobs() == []


def test_increment_job_fail_disables_after_three(user_db):
    job_id = user_db.add_job("0 9 * * *", "test")
    user_db.increment_job_fail(job_id)
    user_db.increment_job_fail(job_id)
    assert len(user_db.list_active_jobs()) == 1  # still active at 2 fails
    user_db.increment_job_fail(job_id)
    assert user_db.list_active_jobs() == []  # disabled at 3


# ── Reminder tools (set / list / cancel) ─────────────────────────────────────

@pytest.fixture
def mock_scheduler():
    s = MagicMock()
    s.add_job = MagicMock()
    s.remove_job = MagicMock()
    return s


@pytest.fixture
def reminder_tools(user_db, mock_scheduler):
    return build_reminder_tools(mock_scheduler, user_db, telegram_id=12345)


def test_set_reminder_creates_db_record(reminder_tools, user_db):
    set_reminder, _, _ = reminder_tools
    result = set_reminder("standup", "every Monday at 9am")
    assert "standup" in result
    jobs = user_db.list_active_jobs()
    assert len(jobs) == 1
    assert jobs[0]["description"] == "standup"


def test_set_reminder_calls_scheduler(reminder_tools, mock_scheduler):
    set_reminder, _, _ = reminder_tools
    set_reminder("every day at 8am", "drink water")
    mock_scheduler.add_job.assert_called_once()
    args = mock_scheduler.add_job.call_args
    assert args[0][0] == 12345  # telegram_id
    assert "8" in args[0][2]    # hour in cron


def test_set_reminder_returns_job_id(reminder_tools):
    set_reminder, _, _ = reminder_tools
    result = set_reminder("every day at 8am", "drink water")
    assert "id:" in result


def test_list_reminders_empty(reminder_tools):
    _, list_reminders, _ = reminder_tools
    assert list_reminders() == "No active reminders."


def test_list_reminders_shows_jobs(reminder_tools, user_db):
    set_reminder, list_reminders, _ = reminder_tools
    set_reminder("standup", "every Monday at 9am")
    result = list_reminders()
    assert "standup" in result
    assert "[1]" in result


def test_cancel_reminder(reminder_tools, user_db, mock_scheduler):
    set_reminder, list_reminders, cancel_reminder = reminder_tools
    set_reminder("every day at 8am", "drink water")
    job_id = user_db.list_active_jobs()[0]["id"]
    result = cancel_reminder(job_id)
    assert str(job_id) in result
    mock_scheduler.remove_job.assert_called_once_with(job_id, telegram_id=12345)
    assert user_db.list_active_jobs() == []


# ── ReminderScheduler ─────────────────────────────────────────────────────────

@pytest.fixture
def scheduler():
    bot = AsyncMock()
    return ReminderScheduler(bot=bot)


def test_scheduler_add_and_remove_job(scheduler):
    scheduler.add_job(telegram_id=1, job_id=42, cron="0 9 * * mon", description="test")
    job = scheduler.scheduler.get_job("job_1_42")
    assert job is not None
    scheduler.remove_job(42, telegram_id=1)
    assert scheduler.scheduler.get_job("job_1_42") is None


def test_scheduler_remove_nonexistent_job_does_not_raise(scheduler):
    scheduler.remove_job(9999)  # should not raise


def test_send_reminder_success(scheduler):
    scheduler.bot.send_message = AsyncMock()
    asyncio.run(scheduler._send_reminder(telegram_id=1, job_id=1, description="test"))
    scheduler.bot.send_message.assert_awaited_once_with(chat_id=1, text="⏰ Reminder: test")


def test_send_reminder_failure_increments_fail(scheduler, tmp_path):
    db_path = str(tmp_path / "conversations.db")
    db = UserDB(db_path)
    job_id = db.add_job("0 9 * * *", "test")

    scheduler.bot.send_message = AsyncMock(side_effect=Exception("network error"))
    asyncio.run(scheduler._send_reminder(
        telegram_id=1, job_id=job_id, description="test", db_path=db_path
    ))
    # After one failure job is still active
    assert len(db.list_active_jobs()) == 1


def test_send_reminder_failure_disables_after_three(scheduler, tmp_path):
    db_path = str(tmp_path / "conversations.db")
    db = UserDB(db_path)
    job_id = db.add_job("0 9 * * *", "test")

    scheduler.bot.send_message = AsyncMock(side_effect=Exception("network error"))
    for _ in range(3):
        asyncio.run(scheduler._send_reminder(
            telegram_id=1, job_id=job_id, description="test", db_path=db_path
        ))
    assert db.list_active_jobs() == []


# ── parse_reminder_request edge cases ────────────────────────────────────────

def test_parse_midnight():
    result = parse_reminder_request("every day at 12am")
    parts = result["cron"].split()
    assert parts[1] == "0"


def test_parse_noon():
    result = parse_reminder_request("every day at 12pm")
    parts = result["cron"].split()
    assert parts[1] == "12"


def test_parse_with_minutes():
    result = parse_reminder_request("every day at 9:30am")
    parts = result["cron"].split()
    assert parts[0] == "30"
    assert parts[1] == "9"
