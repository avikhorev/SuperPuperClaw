import pytest
from bot.db import GlobalDB

@pytest.fixture
def global_db(tmp_path):
    return GlobalDB(str(tmp_path / "global.db"))

def test_first_start_creates_admin(global_db):
    global_db.register_user(telegram_id=100, username="admin")
    user = global_db.get_user(100)
    assert user["is_admin"] == 1
    assert user["status"] == "approved"

def test_second_user_is_pending(global_db):
    global_db.register_user(telegram_id=100, username="admin")
    global_db.register_user(telegram_id=200, username="user2")
    assert global_db.get_user(200)["status"] == "pending"

def test_banned_user_blocked(global_db):
    global_db.register_user(telegram_id=100, username="admin")
    global_db.register_user(telegram_id=200, username="user2")
    global_db.ban_user(200)
    assert global_db.get_user(200)["status"] == "banned"

def test_unapproved_user_not_approved(global_db):
    global_db.register_user(telegram_id=100, username="admin")
    global_db.register_user(telegram_id=200, username="user2")
    user = global_db.get_user(200)
    assert user["status"] != "approved"

def test_approve_changes_status(global_db):
    global_db.register_user(telegram_id=100, username="admin")
    global_db.register_user(telegram_id=200, username="user2")
    global_db.approve_user(200)
    assert global_db.get_user(200)["status"] == "approved"
