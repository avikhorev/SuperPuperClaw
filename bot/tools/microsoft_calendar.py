"""Microsoft Graph API calendar tools."""
import json
import urllib.request
import urllib.parse


GRAPH = "https://graph.microsoft.com/v1.0"


def _get(url: str, token: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _post(url: str, token: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _patch(url: str, token: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method="PATCH", headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _delete(url: str, token: str):
    req = urllib.request.Request(url, method="DELETE", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=15):
        pass


def _manager_and_token(storage):
    tokens = storage.load_microsoft_tokens()
    if not tokens:
        return None, None
    from bot.microsoft_oauth import MicrosoftOAuthManager
    from bot.config import Config
    config = Config()
    mgr = MicrosoftOAuthManager(config.microsoft_client_id, config.microsoft_client_secret)
    return mgr, mgr.get_access_token(tokens, storage)


def list_calendar_events_microsoft(days_ahead: int = 7, storage=None) -> str:
    """List upcoming Outlook calendar events for the next N days."""
    mgr, token = _manager_and_token(storage)
    if not token:
        return "Microsoft account not connected. Use /connect microsoft."
    try:
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days_ahead)
        start_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_str = end.strftime("%Y-%m-%dT%H:%M:%SZ")
        url = (f"{GRAPH}/me/calendarView"
               f"?startDateTime={start_str}&endDateTime={end_str}"
               f"&$select=id,subject,start,end,bodyPreview"
               f"&$orderby=start/dateTime"
               f"&$top=50")
        data = _get(url, token)
        events = data.get("value", [])
        if not events:
            return f"No events in the next {days_ahead} days."
        lines = []
        for e in events:
            start = e.get("start", {}).get("dateTime", "")[:16].replace("T", " ")
            lines.append(f"• [id:{e['id'][-8:]}] {e.get('subject','(no title)')} — {start}")
        return "\n".join(lines)
    except Exception as e:
        return f"Calendar unavailable: {e}"


list_calendar_events_microsoft._needs_storage = True


def create_calendar_event_microsoft(title: str, start: str, end: str, description: str = "", storage=None) -> str:
    """Create an Outlook calendar event. start/end in ISO format e.g. '2026-03-06T15:00:00'"""
    mgr, token = _manager_and_token(storage)
    if not token:
        return "Microsoft account not connected."
    try:
        event = _post(f"{GRAPH}/me/events", token, {
            "subject": title,
            "body": {"contentType": "Text", "content": description},
            "start": {"dateTime": start, "timeZone": "UTC"},
            "end": {"dateTime": end, "timeZone": "UTC"},
        })
        return f"Event '{title}' created."
    except Exception as e:
        return f"Could not create event: {e}"


create_calendar_event_microsoft._needs_storage = True


def update_calendar_event_microsoft(event_id_suffix: str, title: str = "", start: str = "", end: str = "", description: str = "", storage=None) -> str:
    """Update an Outlook calendar event by id suffix (shown in list_calendar_events_microsoft as [id:XXXXXXXX])."""
    mgr, token = _manager_and_token(storage)
    if not token:
        return "Microsoft account not connected."
    try:
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        end_search = now + timedelta(days=90)
        url = (f"{GRAPH}/me/calendarView"
               f"?startDateTime={now.strftime('%Y-%m-%dT%H:%M:%SZ')}"
               f"&endDateTime={end_search.strftime('%Y-%m-%dT%H:%M:%SZ')}"
               f"&$select=id&$top=100")
        data = _get(url, token)
        event = next((e for e in data.get("value", []) if e["id"].endswith(event_id_suffix)), None)
        if not event:
            return "Event not found."
        body = {}
        if title:
            body["subject"] = title
        if description:
            body["body"] = {"contentType": "Text", "content": description}
        if start:
            body["start"] = {"dateTime": start, "timeZone": "UTC"}
        if end:
            body["end"] = {"dateTime": end, "timeZone": "UTC"}
        _patch(f"{GRAPH}/me/events/{event['id']}", token, body)
        return "Event updated."
    except Exception as e:
        return f"Could not update event: {e}"


update_calendar_event_microsoft._needs_storage = True


def delete_calendar_event_microsoft(event_id_suffix: str, storage=None) -> str:
    """Delete an Outlook calendar event by id suffix (shown in list_calendar_events_microsoft as [id:XXXXXXXX])."""
    mgr, token = _manager_and_token(storage)
    if not token:
        return "Microsoft account not connected."
    try:
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        end_search = now + timedelta(days=90)
        url = (f"{GRAPH}/me/calendarView"
               f"?startDateTime={now.strftime('%Y-%m-%dT%H:%M:%SZ')}"
               f"&endDateTime={end_search.strftime('%Y-%m-%dT%H:%M:%SZ')}"
               f"&$select=id&$top=100")
        data = _get(url, token)
        event = next((e for e in data.get("value", []) if e["id"].endswith(event_id_suffix)), None)
        if not event:
            return "Event not found."
        _delete(f"{GRAPH}/me/events/{event['id']}", token)
        return "Event deleted."
    except Exception as e:
        return f"Could not delete event: {e}"


delete_calendar_event_microsoft._needs_storage = True
