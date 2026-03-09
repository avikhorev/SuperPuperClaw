import os
import pytest
from types import SimpleNamespace
from bot.config import Config
from bot.db import GlobalDB
from bot.storage import UserStorage
from bot.handler import BotHandler
from tests.integration.fakes import FakeScheduler, FakeUpdate, FakeContext


ADMIN_ID = 100
USER_ID = 200


@pytest.fixture
def fake_scheduler():
    return FakeScheduler()


@pytest.fixture
def global_db(tmp_path):
    db = GlobalDB(str(tmp_path / "global.db"))
    db.register_user(telegram_id=ADMIN_ID, username="admin")  # first user = admin
    return db


@pytest.fixture
def config(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "test-token")
    cfg = Config()
    cfg.data_dir = str(tmp_path / "data")
    return cfg


@pytest.fixture
def handler(config, global_db, fake_scheduler):
    return BotHandler(config=config, global_db=global_db, scheduler=fake_scheduler)


@pytest.fixture
def approved_user(global_db):
    global_db.register_user(telegram_id=USER_ID, username="alice")
    global_db.approve_user(USER_ID)
    return USER_ID


def make_update(text="", user_id=USER_ID):
    return FakeUpdate(text=text, user_id=user_id)


def make_ctx():
    return FakeContext()
