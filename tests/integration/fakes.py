"""Fake Telegram and scheduler objects for integration testing."""
from types import SimpleNamespace
from unittest.mock import AsyncMock


class FakeMessage:
    def __init__(self, text: str):
        self.text = text
        self.voice = None
        self.document = None
        self.replies: list[str] = []

    async def reply_text(self, text, **kwargs):
        self.replies.append(text)


class FakeUser:
    def __init__(self, user_id: int = 1, username: str = "testuser"):
        self.id = user_id
        self.username = username


class FakeUpdate:
    def __init__(self, text: str = "", user_id: int = 1, username: str = "testuser"):
        self.effective_user = FakeUser(user_id, username)
        self.message = FakeMessage(text)


class FakeBot:
    def __init__(self):
        self.sent: list[dict] = []  # {"chat_id": ..., "text": ...}

    async def send_message(self, chat_id, text, **kwargs):
        self.sent.append({"chat_id": chat_id, "text": text})

    async def send_chat_action(self, chat_id, action):
        pass


class FakeContext:
    def __init__(self):
        self.user_data: dict = {}
        self.args: list[str] = []
        self.bot = FakeBot()


class FakeScheduler:
    """Minimal scheduler that records jobs without requiring an event loop."""
    def __init__(self):
        self.jobs: dict[str, dict] = {}  # job_id -> {telegram_id, cron, description}
        self.scheduler = self  # so scheduler.scheduler.add_job works too

    def add_job(self, telegram_id, job_id, cron, description, db_path=None):
        self.jobs[str(job_id)] = {
            "telegram_id": telegram_id,
            "job_id": job_id,
            "cron": cron,
            "description": description,
        }

    def remove_job(self, job_id):
        self.jobs.pop(str(job_id), None)

    def start(self):
        pass

    def get_jobs(self):
        return list(self.jobs.values())
