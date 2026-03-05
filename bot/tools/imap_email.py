"""Email tools using IMAP (read) and SMTP (send). No external packages required."""
import imaplib
import smtplib
import email as email_lib
import ssl
from email.mime.text import MIMEText
from email.header import decode_header as _decode_header


def _decode(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    parts = _decode_header(value)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


def _get_imap_config(storage) -> dict | None:
    return storage.load_imap_config()


def list_emails_imap(max_results: int = 10, query: str = "ALL", storage=None) -> str:
    """List recent emails from your inbox. query supports IMAP search e.g. 'UNSEEN', 'FROM boss@example.com'."""
    cfg = _get_imap_config(storage)
    if not cfg:
        return "Email not connected. Use /connect email."
    try:
        ctx = ssl.create_default_context()
        with imaplib.IMAP4_SSL(cfg["imap_host"], cfg["imap_port"], ssl_context=ctx) as imap:
            imap.login(cfg["email"], cfg["password"])
            imap.select("INBOX")
            _, data = imap.search(None, query)
            ids = data[0].split()[-max_results:]
            if not ids:
                return "No emails found."
            results = []
            for msg_id in reversed(ids):
                _, raw = imap.fetch(msg_id, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
                headers_raw = raw[0][1]
                msg = email_lib.message_from_bytes(headers_raw)
                subject = _decode(msg.get("Subject", "(no subject)"))
                sender = _decode(msg.get("From", ""))
                date = msg.get("Date", "")
                results.append(f"• {subject}\n  From: {sender}\n  {date}")
            return "\n\n".join(results)
    except Exception as e:
        return f"Email unavailable: {e}"


list_emails_imap._needs_storage = True


def send_email_imap(to: str, subject: str, body: str, storage=None) -> str:
    """Send an email."""
    cfg = _get_imap_config(storage)
    if not cfg:
        return "Email not connected. Use /connect email."
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["From"] = cfg["email"]
        msg["To"] = to
        msg["Subject"] = subject
        ctx = ssl.create_default_context()
        with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"]) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ctx)
            smtp.login(cfg["email"], cfg["password"])
            smtp.sendmail(cfg["email"], [to], msg.as_bytes())
        return f"Email sent to {to}."
    except Exception as e:
        return f"Could not send email: {e}"


send_email_imap._needs_storage = True
