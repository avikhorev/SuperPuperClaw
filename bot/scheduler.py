import re
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

DAY_MAP = {
    "monday": "mon",
    "tuesday": "tue",
    "wednesday": "wed",
    "thursday": "thu",
    "friday": "fri",
    "saturday": "sat",
    "sunday": "sun",
}


def parse_reminder_request(text: str) -> dict | None:
    """Parse a natural language reminder request into a cron expression and description."""
    from datetime import datetime, timezone, timedelta
    text_lower = text.lower()

    # Handle relative time: "in N minutes/hours"
    relative = re.search(r"in\s+(\d+)\s+(minute|minutes|hour|hours)", text_lower)
    if relative:
        amount = int(relative.group(1))
        unit = relative.group(2)
        now = datetime.now(timezone.utc)
        if "hour" in unit:
            target = now + timedelta(hours=amount)
        else:
            target = now + timedelta(minutes=amount)
        cron = f"{target.minute} {target.hour} {target.day} {target.month} *"
        description = re.sub(
            r"remind(?:\s+me)?(\s+to)?|in\s+\d+\s+(?:minute|minutes|hour|hours)",
            "", text, flags=re.IGNORECASE,
        ).strip()
        return {"cron": cron, "description": description or text.strip()}

    # Extract time
    hour = 9
    minute = 0
    time_match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text_lower)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or 0)
        meridiem = time_match.group(3)
        if meridiem == "pm" and hour < 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0

    # Extract day of week
    day_of_week = "*"
    for day_name, abbr in DAY_MAP.items():
        if day_name in text_lower:
            day_of_week = abbr
            break

    cron = f"{minute} {hour} * * {day_of_week}"

    # Extract description: strip the scheduling part
    description = re.sub(
        r"remind(?:\s+me)?|every\s+\w+|at\s+\d+(?::\d+)?\s*(?:am|pm)?",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    if not description:
        description = text.strip()

    return {"cron": cron, "description": description}


class ReminderScheduler:
    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()

    def start(self):
        self.scheduler.start()

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def add_job(self, telegram_id: int, job_id: int, cron: str, description: str, db_path: str = None):
        parts = cron.split()
        trigger = CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
        )
        # Composite ID prevents collision when two users share the same per-user job_id
        scheduler_id = f"job_{telegram_id}_{job_id}"
        self.scheduler.add_job(
            self._send_reminder,
            trigger=trigger,
            args=[telegram_id, job_id, description, db_path],
            id=scheduler_id,
            replace_existing=True,
        )

    def remove_job(self, job_id: int, telegram_id: int = 0):
        try:
            self.scheduler.remove_job(f"job_{telegram_id}_{job_id}")
        except Exception:
            pass

    async def _send_reminder(self, telegram_id: int, job_id: int, description: str, db_path: str = None):
        try:
            await self.bot.send_message(chat_id=telegram_id, text=f"⏰ Reminder: {description}")
        except Exception as e:
            logger.error("Reminder delivery failed for job %s (user %s): %s", job_id, telegram_id, e)
            if db_path:
                try:
                    from bot.db import UserDB
                    UserDB(db_path).increment_job_fail(job_id)
                except Exception:
                    pass
