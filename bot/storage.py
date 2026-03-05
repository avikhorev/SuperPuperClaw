import json
import os
from bot.db import UserDB


class UserStorage:
    def __init__(self, data_dir: str, telegram_id: int):
        self.user_dir = os.path.join(data_dir, "users", str(telegram_id))
        os.makedirs(self.user_dir, exist_ok=True)
        self.db = UserDB(os.path.join(self.user_dir, "conversations.db"))
        self._memory_path = os.path.join(self.user_dir, "memory.md")
        self._tokens_path = os.path.join(self.user_dir, "oauth_tokens.json")

    def read_memory(self) -> str:
        if not os.path.exists(self._memory_path):
            return ""
        with open(self._memory_path) as f:
            return f.read()

    def write_memory(self, content: str):
        with open(self._memory_path, "w") as f:
            f.write(content)

    def load_oauth_tokens(self) -> dict | None:
        if not os.path.exists(self._tokens_path):
            return None
        with open(self._tokens_path) as f:
            return json.load(f)

    def save_oauth_tokens(self, tokens: dict):
        with open(self._tokens_path, "w") as f:
            json.dump(tokens, f)

    def load_imap_config(self) -> dict | None:
        path = os.path.join(self.user_dir, "imap_config.json")
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return json.load(f)

    def save_imap_config(self, config: dict):
        path = os.path.join(self.user_dir, "imap_config.json")
        with open(path, "w") as f:
            json.dump(config, f)

    def load_calendar_config(self) -> dict | None:
        path = os.path.join(self.user_dir, "calendar_config.json")
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return json.load(f)

    def save_calendar_config(self, config: dict):
        path = os.path.join(self.user_dir, "calendar_config.json")
        with open(path, "w") as f:
            json.dump(config, f)

    def delete(self):
        import shutil
        shutil.rmtree(self.user_dir, ignore_errors=True)
