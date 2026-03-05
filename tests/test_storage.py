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

def test_imap_config_absent_by_default(storage):
    assert storage.load_imap_config() is None

def test_save_and_load_imap_config(storage):
    cfg = {"email": "test@gmail.com", "password": "secret", "imap_host": "imap.gmail.com", "imap_port": 993, "smtp_host": "smtp.gmail.com", "smtp_port": 587}
    storage.save_imap_config(cfg)
    loaded = storage.load_imap_config()
    assert loaded["email"] == "test@gmail.com"

def test_calendar_config_absent_by_default(storage):
    assert storage.load_calendar_config() is None

def test_save_and_load_calendar_config(storage):
    storage.save_calendar_config({"ics_url": "https://example.com/calendar.ics"})
    loaded = storage.load_calendar_config()
    assert loaded["ics_url"] == "https://example.com/calendar.ics"
