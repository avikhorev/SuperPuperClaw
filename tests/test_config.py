import os
from bot.config import Config

def test_config_loads_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "test_token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test_key")
    monkeypatch.setenv("DATA_DIR", "/tmp/testdata")
    config = Config()
    assert config.telegram_token == "test_token"
    assert config.anthropic_api_key == "test_key"
    assert config.data_dir == "/tmp/testdata"

def test_config_raises_on_missing_required(monkeypatch):
    monkeypatch.delenv("TELEGRAM_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import pytest
    with pytest.raises(ValueError):
        Config()
