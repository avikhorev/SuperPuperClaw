"""Read-only calendar via ICS URL. Works with Google, Outlook, iCloud, Fastmail, etc."""
import httpx
from datetime import datetime, timezone, timedelta


def list_calendar_events_ics(days_ahead: int = 7, storage=None) -> str:
    """List upcoming calendar events for the next N days."""
    cfg = storage.load_calendar_config() if storage else None
    if not cfg:
        return "Calendar not connected. Use /connect calendar."
    try:
        from icalendar import Calendar
        resp = httpx.get(cfg["ics_url"], timeout=15, follow_redirects=True)
        resp.raise_for_status()
        cal = Calendar.from_ical(resp.content)
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=days_ahead)
        events = []
        for component in cal.walk():
            if component.name != "VEVENT":
                continue
            dtstart = component.get("DTSTART")
            if not dtstart:
                continue
            start = dtstart.dt
            # Handle date-only events
            if not hasattr(start, "tzinfo"):
                start = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
            elif start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            if now <= start <= cutoff:
                summary = str(component.get("SUMMARY", "(no title)"))
                events.append((start, summary))
        if not events:
            return f"No events in the next {days_ahead} days."
        events.sort(key=lambda x: x[0])
        return "\n".join(
            f"• {summary} — {start.strftime('%a %b %d, %H:%M')}"
            for start, summary in events
        )
    except Exception as e:
        return f"Calendar unavailable: {e}"


list_calendar_events_ics._needs_storage = True
