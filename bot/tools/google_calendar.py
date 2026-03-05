from googleapiclient.discovery import build


def list_calendar_events(time_min: str = None, max_results: int = 10, storage=None) -> str:
    """List upcoming Google Calendar events. time_min in ISO format e.g. '2026-03-01T00:00:00Z'"""
    try:
        tokens = storage.load_oauth_tokens()
        if not tokens:
            return "Google not connected."
        from bot.oauth import OAuthManager
        from bot.config import Config
        config = Config()
        creds = OAuthManager(config.google_client_id, config.google_client_secret).get_credentials(tokens)
        service = build("calendar", "v3", credentials=creds)
        from datetime import datetime, timezone
        tmin = time_min or datetime.now(timezone.utc).isoformat()
        events = service.events().list(
            calendarId="primary", timeMin=tmin,
            maxResults=max_results, singleEvents=True, orderBy="startTime"
        ).execute().get("items", [])
        if not events:
            return "No upcoming events."
        return "\n".join(
            f"• {e['summary']} — {e['start'].get('dateTime', e['start'].get('date'))}"
            for e in events
        )
    except Exception as e:
        return f"Calendar unavailable: {e}"


list_calendar_events._needs_storage = True


def create_calendar_event(title: str, start: str, end: str, description: str = "", storage=None) -> str:
    """Create a Google Calendar event. start/end in ISO format e.g. '2026-03-01T09:00:00+00:00'"""
    try:
        tokens = storage.load_oauth_tokens()
        if not tokens:
            return "Google not connected."
        from bot.oauth import OAuthManager
        from bot.config import Config
        config = Config()
        creds = OAuthManager(config.google_client_id, config.google_client_secret).get_credentials(tokens)
        service = build("calendar", "v3", credentials=creds)
        event = service.events().insert(calendarId="primary", body={
            "summary": title,
            "description": description,
            "start": {"dateTime": start},
            "end": {"dateTime": end},
        }).execute()
        return f"Event created: {event.get('htmlLink')}"
    except Exception as e:
        return f"Could not create event: {e}"


create_calendar_event._needs_storage = True
