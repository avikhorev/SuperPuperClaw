"""CalDAV calendar tools — read/write for iCloud, Fastmail, Nextcloud, Google, etc."""
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
    name = cfg.get("calendar_name")
    if name:
        for cal in calendars:
            try:
                cal_name = cal.get_display_name()
            except Exception:
                cal_name = getattr(cal, "name", "")
            if cal_name == name:
                return cal
    return calendars[0]


def _get_vevent(ev):
    """Return the VEVENT icalendar component from a caldav Event object."""
    comp = ev.icalendar_component
    # icalendar_component may be the VEVENT directly or a VCALENDAR wrapper
    if comp.name == "VEVENT":
        return comp
    for sub in comp.walk("VEVENT"):
        return sub
    return None


def _dt_to_aware(dt):
    """Ensure a datetime is timezone-aware."""
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    # date object — convert to datetime
    return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)


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
        items = []
        for ev in events:
            vevent = _get_vevent(ev)
            if vevent is None:
                continue
            summary = str(vevent.get("SUMMARY", "(no title)"))
            start = _dt_to_aware(vevent.get("DTSTART").dt)
            uid_val = str(vevent.get("UID", ""))
            items.append((start, uid_val, summary))
        items.sort(key=lambda x: x[0])
        lines = [f"• [uid:{uid[:8]}] {summary} — {start.strftime('%a %b %d, %H:%M')}"
                 for start, uid, summary in items]
        return "\n".join(lines) if lines else f"No events in the next {days_ahead} days."
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
        cal = _principal_calendar(cfg)
        now = datetime.now(timezone.utc)
        events = cal.search(start=now - timedelta(days=365), end=now + timedelta(days=365), event=True)
        for ev in events:
            vevent = _get_vevent(ev)
            if vevent is None:
                continue
            uid_val = str(vevent.get("UID", ""))
            if uid_val.startswith(uid_prefix):
                ev.delete()
                return "Event deleted."
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
        from icalendar import Calendar, Event
        cal = _principal_calendar(cfg)
        now = datetime.now(timezone.utc)
        events = cal.search(start=now - timedelta(days=365), end=now + timedelta(days=365), event=True)
        for ev in events:
            vevent = _get_vevent(ev)
            if vevent is None:
                continue
            uid_val = str(vevent.get("UID", ""))
            if uid_val.startswith(uid_prefix):
                # Rebuild the ical with updated fields
                cal_obj = Calendar()
                cal_obj.add("prodid", "-//Bot//EN")
                cal_obj.add("version", "2.0")
                new_event = Event()
                new_event.add("uid", uid_val)
                new_event.add("summary", title if title else str(vevent.get("SUMMARY", "")))
                new_event.add("dtstart", datetime.fromisoformat(start) if start else vevent.get("DTSTART").dt)
                new_event.add("dtend", datetime.fromisoformat(end) if end else vevent.get("DTEND").dt)
                desc = description if description else str(vevent.get("DESCRIPTION", ""))
                if desc:
                    new_event.add("description", desc)
                cal_obj.add_component(new_event)
                ev.data = cal_obj.to_ical()
                ev.save()
                return "Event updated."
        return f"No event found with uid starting with '{uid_prefix}'."
    except Exception as e:
        return f"Could not update event: {e}"


update_caldav_event._needs_storage = True
