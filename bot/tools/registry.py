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


def build_tool_registry(user_storage, has_google: bool) -> list:
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
    ]
    if has_google:
        from bot.tools.google_calendar import list_calendar_events, create_calendar_event
        from bot.tools.gmail import list_emails, send_email
        from bot.tools.google_drive import search_drive_files
        tools += [list_calendar_events, create_calendar_event, list_emails, send_email, search_drive_files]
    return tools
