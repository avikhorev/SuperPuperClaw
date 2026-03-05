"""Email tools using IMAP (read) and SMTP (send). No external packages required."""
import imaplib
import smtplib
import email as email_lib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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


def _smtp_connect(cfg: dict):
    ctx = ssl.create_default_context()
    smtp = smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"])
    smtp.ehlo()
    smtp.starttls(context=ctx)
    smtp.login(cfg["email"], cfg["password"])
    return smtp


def list_emails_imap(max_results: int = 10, query: str = "ALL", storage=None) -> str:
    """List recent emails from your inbox. Returns message IDs for use with other tools.
    query supports IMAP search e.g. 'UNSEEN', 'FROM boss@example.com', 'SUBJECT meeting'."""
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
                _, raw = imap.fetch(msg_id, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)])")
                headers_raw = raw[0][1]
                msg = email_lib.message_from_bytes(headers_raw)
                subject = _decode(msg.get("Subject", "(no subject)"))
                sender = _decode(msg.get("From", ""))
                date = msg.get("Date", "")
                mid = msg.get("Message-ID", "")
                results.append(f"• [id:{msg_id.decode()}] {subject}\n  From: {sender}\n  {date}")
            return "\n\n".join(results)
    except Exception as e:
        return f"Email unavailable: {e}"


list_emails_imap._needs_storage = True


def get_email_imap(message_id: str, storage=None) -> str:
    """Read the full body of an email by its id (shown in list_emails_imap as [id:N])."""
    cfg = _get_imap_config(storage)
    if not cfg:
        return "Email not connected. Use /connect email."
    try:
        ctx = ssl.create_default_context()
        with imaplib.IMAP4_SSL(cfg["imap_host"], cfg["imap_port"], ssl_context=ctx) as imap:
            imap.login(cfg["email"], cfg["password"])
            imap.select("INBOX")
            _, raw = imap.fetch(message_id.encode(), "(RFC822)")
            msg = email_lib.message_from_bytes(raw[0][1])
            subject = _decode(msg.get("Subject", "(no subject)"))
            sender = _decode(msg.get("From", ""))
            date = msg.get("Date", "")
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain" and not part.get("Content-Disposition"):
                        body = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="replace")
                        break
            else:
                body = msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", errors="replace")
            return f"From: {sender}\nDate: {date}\nSubject: {subject}\n\n{body}"
    except Exception as e:
        return f"Email unavailable: {e}"


get_email_imap._needs_storage = True


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
        with _smtp_connect(cfg) as smtp:
            smtp.sendmail(cfg["email"], [to], msg.as_bytes())
        return f"Email sent to {to}."
    except Exception as e:
        return f"Could not send email: {e}"


send_email_imap._needs_storage = True


def reply_email_imap(message_id: str, body: str, storage=None) -> str:
    """Reply to an email by its id (shown in list_emails_imap as [id:N])."""
    cfg = _get_imap_config(storage)
    if not cfg:
        return "Email not connected. Use /connect email."
    try:
        ctx = ssl.create_default_context()
        with imaplib.IMAP4_SSL(cfg["imap_host"], cfg["imap_port"], ssl_context=ctx) as imap:
            imap.login(cfg["email"], cfg["password"])
            imap.select("INBOX")
            _, raw = imap.fetch(message_id.encode(), "(RFC822)")
            orig = email_lib.message_from_bytes(raw[0][1])

        reply = MIMEText(body, "plain", "utf-8")
        reply["From"] = cfg["email"]
        reply["To"] = _decode(orig.get("Reply-To") or orig.get("From", ""))
        reply["Subject"] = "Re: " + _decode(orig.get("Subject", ""))
        reply["In-Reply-To"] = orig.get("Message-ID", "")
        reply["References"] = orig.get("Message-ID", "")

        with _smtp_connect(cfg) as smtp:
            smtp.sendmail(cfg["email"], [reply["To"]], reply.as_bytes())
        return f"Reply sent to {reply['To']}."
    except Exception as e:
        return f"Could not send reply: {e}"


reply_email_imap._needs_storage = True


def delete_email_imap(message_id: str, storage=None) -> str:
    """Delete (trash) an email by its id (shown in list_emails_imap as [id:N])."""
    cfg = _get_imap_config(storage)
    if not cfg:
        return "Email not connected. Use /connect email."
    try:
        ctx = ssl.create_default_context()
        with imaplib.IMAP4_SSL(cfg["imap_host"], cfg["imap_port"], ssl_context=ctx) as imap:
            imap.login(cfg["email"], cfg["password"])
            imap.select("INBOX")
            imap.store(message_id.encode(), "+FLAGS", "\\Deleted")
            imap.expunge()
        return f"Email {message_id} deleted."
    except Exception as e:
        return f"Could not delete email: {e}"


delete_email_imap._needs_storage = True


def mark_email_read_imap(message_id: str, storage=None) -> str:
    """Mark an email as read by its id (shown in list_emails_imap as [id:N])."""
    cfg = _get_imap_config(storage)
    if not cfg:
        return "Email not connected. Use /connect email."
    try:
        ctx = ssl.create_default_context()
        with imaplib.IMAP4_SSL(cfg["imap_host"], cfg["imap_port"], ssl_context=ctx) as imap:
            imap.login(cfg["email"], cfg["password"])
            imap.select("INBOX")
            imap.store(message_id.encode(), "+FLAGS", "\\Seen")
        return f"Email {message_id} marked as read."
    except Exception as e:
        return f"Could not mark email: {e}"


mark_email_read_imap._needs_storage = True
