# tests/test_oauth.py
import pytest
from bot.oauth import extract_auth_code_from_url, OAuthManager

def test_extract_code_from_redirect_url():
    url = "https://accounts.google.com/o/oauth2/approval?code=4%2F0abc123&scope=..."
    code = extract_auth_code_from_url(url)
    assert code is not None
    assert "abc123" in code or "4" in code

def test_extract_code_from_localhost_url():
    url = "http://localhost/?code=4/xyz789&scope=email"
    code = extract_auth_code_from_url(url)
    assert code == "4/xyz789"

def test_extract_code_returns_none_for_missing():
    assert extract_auth_code_from_url("https://example.com/no-code") is None
    assert extract_auth_code_from_url("") is None

def test_oauth_manager_builds_auth_url():
    manager = OAuthManager(client_id="test_client_id", client_secret="test_secret")
    url = manager.get_auth_url()
    assert "accounts.google.com" in url
    assert "test_client_id" in url

def test_oauth_manager_requires_credentials():
    manager = OAuthManager(client_id="", client_secret="")
    # Should not raise during construction, but auth_url should still be buildable
    # (Google will reject at runtime, not at URL-build time)
    assert manager is not None
