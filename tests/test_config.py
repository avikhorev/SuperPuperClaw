import os
import pytest
from bot.config import Config

def test_config_loads_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "test_token")
    monkeypatch.setenv("DATA_DIR", "/tmp/testdata")
    config = Config()
    assert config.telegram_token == "test_token"
    assert config.data_dir == "/tmp/testdata"

def test_config_raises_on_missing_required(monkeypatch):
    monkeypatch.delenv("TELEGRAM_TOKEN", raising=False)
    with pytest.raises(ValueError):
        Config()

def test_google_keys_default_to_none(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "tok")
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    config = Config()
    assert config.google_client_id is None
    assert config.google_client_secret is None
