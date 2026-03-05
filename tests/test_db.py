# tests/test_db.py
import os, tempfile, pytest
from bot.db import GlobalDB, UserDB

@pytest.fixture
def global_db(tmp_path):
    return GlobalDB(str(tmp_path / "global.db"))

@pytest.fixture
def user_db(tmp_path):
    return UserDB(str(tmp_path / "conversations.db"))

def test_global_db_creates_tables(global_db):
    users = global_db.list_users()
    assert users == []

def test_register_user(global_db):
    global_db.register_user(telegram_id=1, username="first")  # first user becomes admin
    global_db.register_user(telegram_id=123, username="alice")
    user = global_db.get_user(123)
    assert user["status"] == "pending"
    assert user["is_admin"] == 0

def test_first_user_becomes_admin(global_db):
    global_db.register_user(telegram_id=1, username="first")
    user = global_db.get_user(1)
    assert user["is_admin"] == 1
    assert user["status"] == "approved"

def test_second_user_not_admin(global_db):
    global_db.register_user(telegram_id=1, username="first")
    global_db.register_user(telegram_id=2, username="second")
    user = global_db.get_user(2)
    assert user["is_admin"] == 0
    assert user["status"] == "pending"

def test_approve_user(global_db):
    global_db.register_user(telegram_id=2, username="bob")
    global_db.approve_user(2)
    assert global_db.get_user(2)["status"] == "approved"

def test_ban_user(global_db):
    global_db.register_user(telegram_id=2, username="bob")
    global_db.ban_user(2)
    assert global_db.get_user(2)["status"] == "banned"

def test_user_db_messages(user_db):
    user_db.add_message(role="user", content="hello")
    user_db.add_message(role="assistant", content="hi")
    msgs = user_db.get_recent_messages(10)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"

def test_user_db_jobs(user_db):
    job_id = user_db.add_job(cron="0 9 * * 1", description="standup reminder")
    jobs = user_db.list_active_jobs()
    assert len(jobs) == 1
    assert jobs[0]["id"] == job_id
    user_db.cancel_job(job_id)
    assert user_db.list_active_jobs() == []
