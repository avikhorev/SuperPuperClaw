# tests/test_scheduler.py
import pytest
from bot.scheduler import parse_reminder_request

def test_parse_daily_reminder():
    result = parse_reminder_request("remind me every day at 8am take pills")
    assert result is not None
    assert "cron" in result
    assert "description" in result
    # daily = every day of week
    parts = result["cron"].split()
    assert len(parts) == 5
    assert parts[1] == "8"  # hour = 8

def test_parse_monday_reminder():
    result = parse_reminder_request("every Monday at 9am standup")
    assert result is not None
    parts = result["cron"].split()
    assert parts[1] == "9"
    assert parts[4] == "mon"

def test_parse_pm_time():
    result = parse_reminder_request("every day at 3pm check email")
    assert result is not None
    parts = result["cron"].split()
    assert parts[1] == "15"

def test_parse_returns_description():
    result = parse_reminder_request("remind me every day at 8am take my pills")
    assert result["description"]
    assert len(result["description"]) > 0

def test_parse_default_time():
    # if no time specified, should still return a valid cron
    result = parse_reminder_request("every Monday check emails")
    assert result is not None
    parts = result["cron"].split()
    assert len(parts) == 5
