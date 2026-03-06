"""Microsoft Graph API email tools."""
import json
import urllib.request


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
        return json.loads(r.read()) if r.length else {}


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


def list_emails_microsoft(max_results: int = 10, query: str = "", storage=None) -> str:
    """List recent emails from Outlook inbox. query supports OData filter e.g. 'isRead eq false'"""
    mgr, token = _manager_and_token(storage)
    if not token:
        return "Microsoft account not connected. Use /connect microsoft."
    try:
        url = f"{GRAPH}/me/mailFolders/inbox/messages?$top={max_results}&$select=id,subject,from,receivedDateTime,isRead&$orderby=receivedDateTime desc"
        if query:
            url += f"&$filter={urllib.request.quote(query)}"
        data = _get(url, token)
        msgs = data.get("value", [])
        if not msgs:
            return "No emails found."
        lines = []
        for m in msgs:
            unread = "●" if not m.get("isRead") else " "
            sender = m.get("from", {}).get("emailAddress", {}).get("address", "")
            lines.append(f"{unread} [id:{m['id'][-8:]}] {m.get('subject','(no subject)')}\n  From: {sender}  {m.get('receivedDateTime','')[:10]}")
        return "\n\n".join(lines)
    except Exception as e:
        return f"Email unavailable: {e}"


list_emails_microsoft._needs_storage = True


def get_email_microsoft(message_id_suffix: str, storage=None) -> str:
    """Read full email body. Use the id shown in list_emails_microsoft as [id:XXXXXXXX]."""
    mgr, token = _manager_and_token(storage)
    if not token:
        return "Microsoft account not connected."
    try:
        # Search for message by id suffix
        data = _get(f"{GRAPH}/me/messages?$select=id,subject,from,body,receivedDateTime&$top=50", token)
        msg = next((m for m in data.get("value", []) if m["id"].endswith(message_id_suffix)), None)
        if not msg:
            return f"Message with id ending '{message_id_suffix}' not found."
        sender = msg.get("from", {}).get("emailAddress", {}).get("address", "")
        body = msg.get("body", {}).get("content", "")
        # Strip HTML tags simply
        import re
        body = re.sub(r"<[^>]+>", "", body).strip()
        return f"From: {sender}\nDate: {msg.get('receivedDateTime','')}\nSubject: {msg.get('subject','')}\n\n{body}"
    except Exception as e:
        return f"Email unavailable: {e}"


get_email_microsoft._needs_storage = True


def send_email_microsoft(to: str, subject: str, body: str, storage=None) -> str:
    """Send an email via Outlook."""
    mgr, token = _manager_and_token(storage)
    if not token:
        return "Microsoft account not connected."
    try:
        _post(f"{GRAPH}/me/sendMail", token, {
            "message": {
                "subject": subject,
                "body": {"contentType": "Text", "content": body},
                "toRecipients": [{"emailAddress": {"address": to}}],
            }
        })
        return f"Email sent to {to}."
    except Exception as e:
        return f"Could not send email: {e}"


send_email_microsoft._needs_storage = True


def reply_email_microsoft(message_id_suffix: str, body: str, storage=None) -> str:
    """Reply to an Outlook email by its id (shown in list_emails_microsoft as [id:XXXXXXXX])."""
    mgr, token = _manager_and_token(storage)
    if not token:
        return "Microsoft account not connected."
    try:
        data = _get(f"{GRAPH}/me/messages?$select=id&$top=50", token)
        msg = next((m for m in data.get("value", []) if m["id"].endswith(message_id_suffix)), None)
        if not msg:
            return f"Message not found."
        _post(f"{GRAPH}/me/messages/{msg['id']}/reply", token, {
            "message": {"body": {"contentType": "Text", "content": body}}
        })
        return "Reply sent."
    except Exception as e:
        return f"Could not reply: {e}"


reply_email_microsoft._needs_storage = True


def delete_email_microsoft(message_id_suffix: str, storage=None) -> str:
    """Delete an Outlook email by its id (shown in list_emails_microsoft as [id:XXXXXXXX])."""
    mgr, token = _manager_and_token(storage)
    if not token:
        return "Microsoft account not connected."
    try:
        data = _get(f"{GRAPH}/me/messages?$select=id&$top=50", token)
        msg = next((m for m in data.get("value", []) if m["id"].endswith(message_id_suffix)), None)
        if not msg:
            return "Message not found."
        _delete(f"{GRAPH}/me/messages/{msg['id']}", token)
        return "Email deleted."
    except Exception as e:
        return f"Could not delete: {e}"


delete_email_microsoft._needs_storage = True
