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

def test_caldav_config_absent_by_default(storage):
    assert storage.load_caldav_config() is None

def test_save_and_load_caldav_config(storage):
    cfg = {"caldav_url": "https://caldav.icloud.com", "username": "user@icloud.com", "password": "secret"}
    storage.save_caldav_config(cfg)
    loaded = storage.load_caldav_config()
    assert loaded["caldav_url"] == "https://caldav.icloud.com"
    assert loaded["username"] == "user@icloud.com"

def test_memory_alias_reads_profile(storage):
    storage.write_profile("Name: Test")
    assert storage.read_memory() == "Name: Test"

def test_memory_alias_writes_profile(storage):
    storage.write_memory("Name: Via alias")
    assert storage.read_profile() == "Name: Via alias"

def test_profile_and_context_independent(storage):
    storage.write_profile("profile data")
    storage.write_context("context data")
    assert storage.read_profile() == "profile data"
    assert storage.read_context() == "context data"

def test_profile_overwrite(storage):
    storage.write_profile("v1")
    storage.write_profile("v2")
    assert storage.read_profile() == "v2"

def test_context_overwrite(storage):
    storage.write_context("old context")
    storage.write_context("new context")
    assert storage.read_context() == "new context"
