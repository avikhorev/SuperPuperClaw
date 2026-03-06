import json
import os
from datetime import datetime, timezone
from bot.db import UserDB

DEFAULT_AGENT_RULES = """## Behavior Rules
- Be concise. Use bullet points when listing things.
- Respond in the same language the user writes in.
- Proactively save facts about the user using update_profile.
- Proactively save current working context using update_context.
- Do not use emoji unless the user uses them first.
- When returning an image or file result, just state what it is — no pointing fingers or decorative filler.
- When asked to search the web, ALWAYS call the web_search tool — never answer from memory alone.
- Only generate a QR code when the user explicitly asks for one — do not generate QR codes for flight search links or other URLs unprompted.
"""

DEFAULT_HEARTBEAT = """## Heartbeat Instructions
- Check for any calendar events tomorrow and remind me
- Nothing else for now
"""


class UserStorage:
    def __init__(self, data_dir: str, telegram_id: int):
        self.user_dir = os.path.join(data_dir, "users", str(telegram_id))
        os.makedirs(self.user_dir, exist_ok=True)
        self.db = UserDB(os.path.join(self.user_dir, "conversations.db"))
        self._tokens_path = os.path.join(self.user_dir, "oauth_tokens.json")

    def read_profile(self) -> str:
        path = os.path.join(self.user_dir, "memory", "profile.md")
        if not os.path.exists(path):
            return ""
        with open(path) as f:
            return f.read()

    def write_profile(self, content: str):
        path = os.path.join(self.user_dir, "memory", "profile.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)

    def read_context(self) -> str:
        path = os.path.join(self.user_dir, "memory", "context.md")
        if not os.path.exists(path):
            return ""
        with open(path) as f:
            return f.read()

    def write_context(self, content: str):
        path = os.path.join(self.user_dir, "memory", "context.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)

    def read_agent_rules(self) -> str:
        path = os.path.join(self.user_dir, "memory", "agent.md")
        if not os.path.exists(path):
            return DEFAULT_AGENT_RULES
        with open(path) as f:
            return f.read()

    def write_agent_rules(self, content: str):
        path = os.path.join(self.user_dir, "memory", "agent.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)

    def read_memory(self) -> str:
        return self.read_profile()

    def write_memory(self, content: str):
        self.write_profile(content)

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

    def load_caldav_config(self) -> dict | None:
        path = os.path.join(self.user_dir, "caldav_config.json")
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return json.load(f)

    def load_microsoft_tokens(self) -> dict | None:
        path = os.path.join(self.user_dir, "microsoft_tokens.json")
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return json.load(f)

    def save_microsoft_tokens(self, tokens: dict):
        path = os.path.join(self.user_dir, "microsoft_tokens.json")
        with open(path, "w") as f:
            json.dump(tokens, f)

    def save_caldav_config(self, config: dict):
        path = os.path.join(self.user_dir, "caldav_config.json")
        with open(path, "w") as f:
            json.dump(config, f)

    def append_log(self, user_text: str, assistant_text: str):
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M")
        logs_dir = os.path.join(self.user_dir, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        log_path = os.path.join(logs_dir, f"{date_str}.md")
        entry = f"\n## {time_str} UTC\n**User:** {user_text}\n**Assistant:** {assistant_text}\n"
        with open(log_path, "a") as f:
            f.write(entry)

    def search_logs(self, query: str) -> list[str]:
        logs_dir = os.path.join(self.user_dir, "logs")
        if not os.path.exists(logs_dir):
            return []
        results = []
        query_lower = query.lower()
        for fname in sorted(os.listdir(logs_dir)):
            if not fname.endswith(".md"):
                continue
            date = fname[:-3]
            fpath = os.path.join(logs_dir, fname)
            with open(fpath) as f:
                for line in f:
                    if query_lower in line.lower():
                        results.append(f"[{date}] {line.rstrip()}")
        return results

    def read_heartbeat(self) -> str:
        path = os.path.join(self.user_dir, "memory", "heartbeat.md")
        if not os.path.exists(path):
            return DEFAULT_HEARTBEAT
        with open(path) as f:
            return f.read()

    def write_heartbeat(self, content: str):
        path = os.path.join(self.user_dir, "memory", "heartbeat.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)

    def list_skills(self) -> list[str]:
        skills_dir = os.path.join(self.user_dir, "skills")
        if not os.path.exists(skills_dir):
            return []
        return [f[:-3] for f in os.listdir(skills_dir) if f.endswith(".md")]

    def read_skill(self, name: str) -> str | None:
        path = os.path.join(self.user_dir, "skills", f"{name}.md")
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return f.read()

    def write_skill(self, name: str, content: str):
        skills_dir = os.path.join(self.user_dir, "skills")
        os.makedirs(skills_dir, exist_ok=True)
        with open(os.path.join(skills_dir, f"{name}.md"), "w") as f:
            f.write(content)

    def delete(self):
        import shutil
        shutil.rmtree(self.user_dir, ignore_errors=True)
