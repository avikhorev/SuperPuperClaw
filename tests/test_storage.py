import pytest
from bot.storage import UserStorage

@pytest.fixture
def storage(tmp_path):
    return UserStorage(data_dir=str(tmp_path), telegram_id=42)

def test_creates_user_dir(storage, tmp_path):
    assert (tmp_path / "users" / "42").exists()

def test_memory_empty_by_default(storage):
    assert storage.read_memory() == ""

def test_write_and_read_memory(storage):
    storage.write_memory("- Name: Alex\n- Timezone: UTC")
    assert "Alex" in storage.read_memory()

def test_user_db_accessible(storage):
    storage.db.add_message(role="user", content="hello")
    msgs = storage.db.get_recent_messages(5)
    assert len(msgs) == 1

def test_oauth_tokens_absent_by_default(storage):
    assert storage.load_oauth_tokens() is None

def test_save_and_load_oauth_tokens(storage):
    tokens = {"token": "abc", "refresh_token": "xyz", "expiry": "2030-01-01"}
    storage.save_oauth_tokens(tokens)
    loaded = storage.load_oauth_tokens()
    assert loaded["token"] == "abc"

def test_delete_removes_user_dir(tmp_path):
    s = UserStorage(data_dir=str(tmp_path), telegram_id=99)
    s.write_memory("something")
    s.delete()
    assert not (tmp_path / "users" / "99").exists()
