def build_reminder_tools(scheduler, user_db, telegram_id):
    def set_reminder(description: str, schedule: str) -> str:
        """Set a reminder.

        Args:
            description: What to remind about, e.g. 'drink water', 'call dentist'
            schedule: When to remind. Examples:
                - Relative: 'in 5 minutes', 'in 2 hours'
                - Daily: 'every day at 9am', 'every day at 14:30'
                - Weekly: 'every Monday at 9am', 'every Friday at 17:00'
        """
        from bot.scheduler import parse_reminder_request
        # Pass full combined text so relative times like 'in N minutes' are parsed correctly
        parsed = parse_reminder_request(f"{description} {schedule}")
        job_id = user_db.add_job(parsed["cron"], description)
        scheduler.add_job(telegram_id, job_id, parsed["cron"], description, db_path=user_db.path)
        return f"Reminder set: '{description}' — cron: '{parsed['cron']}' (id: {job_id})"

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
