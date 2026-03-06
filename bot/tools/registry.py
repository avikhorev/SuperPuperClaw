from bot.tools.web_search import web_search
from bot.tools.web_reader import read_webpage
from bot.tools.wikipedia import search_wikipedia
from bot.tools.youtube import get_youtube_transcript
from bot.tools.arxiv import search_arxiv
from bot.tools.news import get_news
from bot.tools.weather import get_weather
from bot.tools.currency import convert_currency
from bot.tools.url_shortener import shorten_url
from bot.tools.qrcode_tool import generate_qr
from bot.tools.pdf_tool import extract_pdf_text
from bot.tools.flights import search_flights


def build_tool_registry(user_storage, scheduler=None, telegram_id=None, has_google: bool = False) -> list:
    tools = [
        web_search,
        read_webpage,
        search_wikipedia,
        get_youtube_transcript,
        search_arxiv,
        get_news,
        get_weather,
        convert_currency,
        shorten_url,
        generate_qr,
        extract_pdf_text,
        search_flights,
    ]

    if user_storage is not None:
        if user_storage.load_imap_config():
            from bot.tools.imap_email import (
                list_emails_imap, get_email_imap, send_email_imap,
                reply_email_imap, delete_email_imap, mark_email_read_imap,
            )
            tools += [list_emails_imap, get_email_imap, send_email_imap,
                      reply_email_imap, delete_email_imap, mark_email_read_imap]
        if user_storage.load_calendar_config():
            from bot.tools.ics_calendar import list_calendar_events_ics
            tools.append(list_calendar_events_ics)
        if user_storage.load_caldav_config():
            from bot.tools.caldav_calendar import (
                list_caldav_events, create_caldav_event,
                update_caldav_event, delete_caldav_event,
            )
            tools += [list_caldav_events, create_caldav_event, update_caldav_event, delete_caldav_event]

    if scheduler is not None and telegram_id is not None:
        from bot.tools.reminders import build_reminder_tools
        tools += build_reminder_tools(scheduler, user_storage.db, telegram_id)

    from bot.tools.logs_tool import build_logs_tools
    if user_storage is not None:
        tools += build_logs_tools(user_storage)

    if user_storage is not None:
        from bot.tools.skills_tool import build_skills_tools
        tools += build_skills_tools(user_storage)

    return tools
