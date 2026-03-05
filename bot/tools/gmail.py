import base64
import email.message
from googleapiclient.discovery import build


def list_emails(max_results: int = 10, query: str = "", storage=None) -> str:
    """List recent emails. query supports Gmail search syntax e.g. 'is:unread from:boss'"""
    try:
        tokens = storage.load_oauth_tokens()
        if not tokens:
            return "Google not connected."
        from bot.oauth import OAuthManager
        from bot.config import Config
        config = Config()
        creds = OAuthManager(config.google_client_id, config.google_client_secret).get_credentials(tokens)
        service = build("gmail", "v1", credentials=creds)
        msgs = service.users().messages().list(
            userId="me", q=query, maxResults=max_results
        ).execute().get("messages", [])
        result = []
        for m in msgs[:10]:
            detail = service.users().messages().get(
                userId="me", id=m["id"], format="metadata",
                metadataHeaders=["Subject", "From"]
            ).execute()
            headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
            result.append(f"• {headers.get('Subject', '(no subject)')} — from {headers.get('From', '')}")
        return "\n".join(result) if result else "No emails found."
    except Exception as e:
        return f"Gmail unavailable: {e}"


list_emails._needs_storage = True


def send_email(to: str, subject: str, body: str, storage=None) -> str:
    """Send an email via Gmail."""
    try:
        tokens = storage.load_oauth_tokens()
        if not tokens:
            return "Google not connected."
        from bot.oauth import OAuthManager
        from bot.config import Config
        config = Config()
        creds = OAuthManager(config.google_client_id, config.google_client_secret).get_credentials(tokens)
        service = build("gmail", "v1", credentials=creds)
        msg = email.message.EmailMessage()
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return f"Email sent to {to}."
    except Exception as e:
        return f"Could not send email: {e}"


send_email._needs_storage = True
