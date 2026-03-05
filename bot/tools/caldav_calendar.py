"""CalDAV calendar tools — read/write for iCloud, Fastmail, Nextcloud, etc."""
from datetime import datetime, timezone, timedelta
import uuid


def _client(cfg: dict):
    import caldav
    return caldav.DAVClient(
        url=cfg["caldav_url"],
        username=cfg["username"],
        password=cfg["password"],
    )


def _principal_calendar(cfg: dict):
    client = _client(cfg)
    principal = client.principal()
    calendars = principal.calendars()
    if not calendars:
        raise ValueError("No calendars found on this CalDAV server.")
    # Prefer calendar matching saved name, otherwise first
    name = cfg.get("calendar_name")
    if name:
        for cal in calendars:
            if cal.name == name:
                return cal
    return calendars[0]


def list_caldav_events(days_ahead: int = 7, storage=None) -> str:
    """List upcoming CalDAV calendar events for the next N days."""
    cfg = storage.load_caldav_config() if storage else None
    if not cfg:
        return "CalDAV calendar not connected. Use /connect caldav."
    try:
        cal = _principal_calendar(cfg)
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days_ahead)
        events = cal.search(start=now, end=end, event=True, expand=True)
        if not events:
            return f"No events in the next {days_ahead} days."
        lines = []
        for ev in sorted(events, key=lambda e: e.vobject_instance.vevent.dtstart.value):
            vevent = ev.vobject_instance.vevent
            summary = str(getattr(vevent, "summary", type("", (), {"value": "(no title)"})()).value)
            start = vevent.dtstart.value
            if not hasattr(start, "tzinfo"):
                from datetime import date
                start = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
            elif start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            uid_val = str(getattr(vevent, "uid", type("", (), {"value": ""})()).value)
            lines.append(f"• [uid:{uid_val[:8]}] {summary} — {start.strftime('%a %b %d, %H:%M')}")
        return "\n".join(lines)
    except Exception as e:
        return f"CalDAV unavailable: {e}"


list_caldav_events._needs_storage = True


def create_caldav_event(title: str, start: str, end: str, description: str = "", storage=None) -> str:
    """Create a CalDAV calendar event. start/end in ISO format e.g. '2026-03-06T15:00:00+01:00'"""
    cfg = storage.load_caldav_config() if storage else None
    if not cfg:
        return "CalDAV calendar not connected. Use /connect caldav."
    try:
        from icalendar import Calendar, Event
        cal_obj = Calendar()
        cal_obj.add("prodid", "-//Bot//EN")
        cal_obj.add("version", "2.0")
        event = Event()
        event.add("summary", title)
        event.add("dtstart", datetime.fromisoformat(start))
        event.add("dtend", datetime.fromisoformat(end))
        if description:
            event.add("description", description)
        event.add("uid", str(uuid.uuid4()))
        cal_obj.add_component(event)
        cal = _principal_calendar(cfg)
        cal.save_event(cal_obj.to_ical())
        return f"Event '{title}' created."
    except Exception as e:
        return f"Could not create event: {e}"


create_caldav_event._needs_storage = True


def delete_caldav_event(uid_prefix: str, storage=None) -> str:
    """Delete a CalDAV event by its uid prefix (shown in list_caldav_events as [uid:XXXXXXXX])."""
    cfg = storage.load_caldav_config() if storage else None
    if not cfg:
        return "CalDAV calendar not connected. Use /connect caldav."
    try:
        from datetime import date
        cal = _principal_calendar(cfg)
        now = datetime.now(timezone.utc)
        events = cal.search(start=now - timedelta(days=365), end=now + timedelta(days=365), event=True)
        for ev in events:
            vevent = ev.vobject_instance.vevent
            uid_val = str(getattr(vevent, "uid", type("", (), {"value": ""})()).value)
            if uid_val.startswith(uid_prefix):
                ev.delete()
                return f"Event deleted."
        return f"No event found with uid starting with '{uid_prefix}'."
    except Exception as e:
        return f"Could not delete event: {e}"


delete_caldav_event._needs_storage = True


def update_caldav_event(uid_prefix: str, title: str = "", start: str = "", end: str = "", description: str = "", storage=None) -> str:
    """Update a CalDAV event by uid prefix. Only provided fields are changed."""
    cfg = storage.load_caldav_config() if storage else None
    if not cfg:
        return "CalDAV calendar not connected. Use /connect caldav."
    try:
        cal = _principal_calendar(cfg)
        now = datetime.now(timezone.utc)
        events = cal.search(start=now - timedelta(days=365), end=now + timedelta(days=365), event=True)
        for ev in events:
            vevent = ev.vobject_instance.vevent
            uid_val = str(getattr(vevent, "uid", type("", (), {"value": ""})()).value)
            if uid_val.startswith(uid_prefix):
                if title:
                    vevent.summary.value = title
                if start:
                    vevent.dtstart.value = datetime.fromisoformat(start)
                if end:
                    vevent.dtend.value = datetime.fromisoformat(end)
                if description:
                    if hasattr(vevent, "description"):
                        vevent.description.value = description
                    else:
                        from vobject.icalendar import RecurringComponent
                        vevent.add("description").value = description
                ev.save()
                return "Event updated."
        return f"No event found with uid starting with '{uid_prefix}'."
    except Exception as e:
        return f"Could not update event: {e}"


update_caldav_event._needs_storage = True
