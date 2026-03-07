import sqlite3
from datetime import datetime, timezone
from typing import Optional


class GlobalDB:
    def __init__(self, path: str):
        self.path = path
        self._init()

    def _conn(self):
        # Short-lived connections per operation: safe for concurrent async use and
        # acceptable at current scale (~50-100 users).
        # TODO: consider a connection pool if query latency becomes measurable under load.
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    username    TEXT,
                    status      TEXT DEFAULT 'pending',
                    is_admin    INTEGER DEFAULT 0,
                    created_at  TEXT
                )
            """)

    def get_user(self, telegram_id: int) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
            ).fetchone()
            return dict(row) if row else None

    def register_user(self, telegram_id: int, username: str):
        if self.get_user(telegram_id):
            return
        is_first = not self.list_users()
        status = "approved" if is_first else "pending"
        is_admin = 1 if is_first else 0
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO users (telegram_id, username, status, is_admin, created_at) VALUES (?,?,?,?,?)",
                (telegram_id, username, status, is_admin, datetime.now(timezone.utc).isoformat())
            )

    def approve_user(self, telegram_id: int):
        with self._conn() as conn:
            conn.execute("UPDATE users SET status='approved' WHERE telegram_id=?", (telegram_id,))

    def ban_user(self, telegram_id: int):
        with self._conn() as conn:
            conn.execute("UPDATE users SET status='banned' WHERE telegram_id=?", (telegram_id,))

    def delete_user(self, telegram_id: int):
        with self._conn() as conn:
            conn.execute("DELETE FROM users WHERE telegram_id=?", (telegram_id,))

    def list_users(self, status: str = None) -> list[dict]:
        with self._conn() as conn:
            if status:
                rows = conn.execute("SELECT * FROM users WHERE status=?", (status,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM users").fetchall()
            return [dict(r) for r in rows]

    def get_admin(self) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE is_admin=1").fetchone()
            return dict(row) if row else None


class UserDB:
    def __init__(self, path: str):
        self.path = path
        self._init()

    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    role      TEXT,
                    content   TEXT,
                    timestamp TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    cron        TEXT,
                    description TEXT,
                    next_run    TEXT,
                    active      INTEGER DEFAULT 1,
                    fail_count  INTEGER DEFAULT 0
                )
            """)

    def add_message(self, role: str, content: str):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO messages (role, content, timestamp) VALUES (?,?,?)",
                (role, content, datetime.now(timezone.utc).isoformat())
            )

    def get_recent_messages(self, n: int) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM messages ORDER BY id DESC LIMIT ?", (n,)
            ).fetchall()
            return [dict(r) for r in reversed(rows)]

    def add_job(self, cron: str, description: str) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO jobs (cron, description, active) VALUES (?,?,1)",
                (cron, description)
            )
            return cur.lastrowid

    def list_active_jobs(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM jobs WHERE active=1").fetchall()
            return [dict(r) for r in rows]

    def cancel_job(self, job_id: int):
        with self._conn() as conn:
            conn.execute("UPDATE jobs SET active=0 WHERE id=?", (job_id,))

    def increment_job_fail(self, job_id: int):
        with self._conn() as conn:
            conn.execute("UPDATE jobs SET fail_count = fail_count + 1 WHERE id=?", (job_id,))
            conn.execute("UPDATE jobs SET active=0 WHERE id=? AND fail_count >= 3", (job_id,))
