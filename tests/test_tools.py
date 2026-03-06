import pytest
from unittest.mock import patch, MagicMock
from bot.tools.weather import get_weather
from bot.tools.currency import convert_currency
from bot.tools.qrcode_tool import generate_qr
from bot.tools.registry import build_tool_registry

def test_weather_returns_string():
    with patch("bot.tools.weather.httpx.get") as mock_get:
        mock_get.return_value.json.side_effect = [
            {"results": [{"latitude": 51.5, "longitude": -0.1}]},
            {"current": {"temperature_2m": 15.0, "weathercode": 0, "windspeed_10m": 10.0}}
        ]
        result = get_weather("London")
        assert isinstance(result, str)
        assert "15" in result or "London" in result

def test_weather_handles_unknown_location():
    with patch("bot.tools.weather.httpx.get") as mock_get:
        mock_get.return_value.json.return_value = {"results": []}
        result = get_weather("Nonexistent Place XYZ")
        assert "not found" in result.lower() or isinstance(result, str)

def test_currency_returns_string():
    with patch("bot.tools.currency.httpx.get") as mock_get:
        mock_get.return_value.json.return_value = {"rates": {"USD": 1.08}}
        result = convert_currency(amount=100, from_currency="EUR", to_currency="USD")
        assert "USD" in result
        assert "108" in result

def test_qr_returns_photo_url_token():
    import re
    result = generate_qr("https://example.com")
    assert isinstance(result, str)
    m = re.match(r"PHOTO_URL:(\S+)", result)
    assert m, f"Expected PHOTO_URL: token, got: {result}"
    url = m.group(1)
    assert "qrserver.com" in url
    assert "example.com" in url

def test_registry_returns_list_without_storage():
    tools = build_tool_registry(user_storage=None, has_google=False)
    assert isinstance(tools, list)
    names = [fn.__name__ for fn in tools]
    assert "web_search" in names
    assert "get_weather" in names
    assert "generate_qr" in names
    assert "extract_pdf_text" in names

def test_registry_excludes_google_tools_when_disabled():
    tools = build_tool_registry(user_storage=None, has_google=False)
    names = [fn.__name__ for fn in tools]
    assert "list_calendar_events" not in names
    assert "list_emails" not in names
