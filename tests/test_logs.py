import os
import pytest
from datetime import datetime, timezone
from unittest.mock import patch
from bot.storage import UserStorage
from bot.tools.logs_tool import build_logs_tools


@pytest.fixture
def storage(tmp_path):
    return UserStorage(data_dir=str(tmp_path), telegram_id=12345)


def test_append_log_creates_file(storage):
    storage.append_log("hello", "hi there")
    logs_dir = os.path.join(storage.user_dir, "logs")
    files = os.listdir(logs_dir)
    assert len(files) == 1
    assert files[0].endswith(".md")


def test_append_log_format(storage):
    storage.append_log("remind me to call dentist", "Reminder set for every Monday at 9am")
    logs_dir = os.path.join(storage.user_dir, "logs")
    fname = os.listdir(logs_dir)[0]
    content = open(os.path.join(logs_dir, fname)).read()
    assert "**User:** remind me to call dentist" in content
    assert "**Assistant:** Reminder set for every Monday at 9am" in content
    assert "UTC" in content


def test_search_logs_finds_match(storage):
    storage.append_log("call dentist", "Reminder set")
    results = storage.search_logs("dentist")
    assert len(results) > 0
    assert "dentist" in results[0].lower()


def test_search_logs_no_match(storage):
    storage.append_log("call dentist", "Reminder set")
    results = storage.search_logs("xyznonexistent")
    assert results == []


def test_search_logs_across_multiple_days(storage):
    fixed_day1 = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    fixed_day2 = datetime(2024, 1, 2, 10, 0, tzinfo=timezone.utc)
    with patch("bot.storage.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_day1
        storage.append_log("first day message", "first day reply")
    with patch("bot.storage.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_day2
        storage.append_log("second day message", "second day reply")
    results = storage.search_logs("day message")
    assert len(results) >= 2


def test_search_logs_tool_no_match(storage):
    tools = build_logs_tools(storage)
    search_fn = tools[0]
    result = search_fn("nonexistent_query_xyz")
    assert "No results found" in result


def test_search_logs_tool_finds_match(storage):
    storage.append_log("weather today", "It's sunny")
    tools = build_logs_tools(storage)
    search_fn = tools[0]
    result = search_fn("weather")
    assert "weather" in result.lower()


def test_append_multiple_logs_same_day(storage):
    storage.append_log("first message", "first reply")
    storage.append_log("second message", "second reply")
    logs_dir = os.path.join(storage.user_dir, "logs")
    assert len(os.listdir(logs_dir)) == 1  # still one file
    content = open(os.path.join(logs_dir, os.listdir(logs_dir)[0])).read()
    assert "first message" in content
    assert "second message" in content


def test_search_logs_case_insensitive(storage):
    storage.append_log("Meeting with Bob", "Noted")
    results = storage.search_logs("meeting")
    assert len(results) > 0
    results2 = storage.search_logs("MEETING")
    assert len(results2) > 0


def test_search_logs_returns_date_prefix(storage):
    storage.append_log("test query", "response")
    results = storage.search_logs("test query")
    assert any(r.startswith("[") for r in results)  # date prefix like [2026-03-05]


def test_search_logs_matches_assistant_text(storage):
    storage.append_log("what's the weather", "It is 22 degrees and sunny")
    results = storage.search_logs("sunny")
    assert len(results) > 0


def test_search_logs_no_logs_dir(storage):
    # No logs written yet — should return empty list without error
    results = storage.search_logs("anything")
    assert results == []


def test_search_logs_result_includes_date(storage):
    fixed_day = datetime(2025, 6, 15, 12, 0, tzinfo=timezone.utc)
    with patch("bot.storage.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_day
        storage.append_log("dentist appointment", "Saved")
    results = storage.search_logs("dentist")
    assert any("2025-06-15" in r for r in results)
