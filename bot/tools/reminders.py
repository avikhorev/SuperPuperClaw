def build_reminder_tools(scheduler, user_db, telegram_id):
    def set_reminder(schedule: str, description: str) -> str:
        """Set a recurring reminder. 'schedule' is natural language like 'every Monday at 9am' or 'every day at 8am'."""
        from bot.scheduler import parse_reminder_request
        parsed = parse_reminder_request(schedule)
        job_id = user_db.add_job(parsed["cron"], description)
        scheduler.add_job(telegram_id, job_id, parsed["cron"], description, db_path=user_db.path)
        return f"Reminder set: '{description}' — schedule: '{parsed['cron']}' (id: {job_id})"

    def list_reminders() -> str:
        """List all active reminders for this user."""
        jobs = user_db.list_active_jobs()
        if not jobs:
            return "No active reminders."
        return "\n".join(f"[{j['id']}] {j['description']} ({j['cron']})" for j in jobs)

    def cancel_reminder(reminder_id: int) -> str:
        """Cancel a reminder by its ID."""
        user_db.cancel_job(reminder_id)
        scheduler.remove_job(reminder_id)
        return f"Reminder {reminder_id} cancelled."

    return [set_reminder, list_reminders, cancel_reminder]
