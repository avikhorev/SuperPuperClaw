import re
import time
import urllib.parse
import urllib.request
import json


SCOPES = [
    "offline_access",
    "User.Read",
    "Mail.ReadWrite",
    "Mail.Send",
    "Calendars.ReadWrite",
]

REDIRECT_URI = "https://login.microsoftonline.com/common/oauth2/nativeclient"
AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"


def extract_auth_code_from_url(url: str) -> str | None:
    if not url:
        return None
    url = urllib.parse.unquote(url)
    match = re.search(r"[?&]code=([^&\s]+)", url)
    return match.group(1) if match else None


class MicrosoftOAuthManager:
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret

    def get_auth_url(self) -> str:
        params = urllib.parse.urlencode({
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": " ".join(SCOPES),
            "response_mode": "query",
            "prompt": "consent",
        })
        return f"{AUTH_URL}?{params}"

    def exchange_code(self, code: str) -> dict:
        data = urllib.parse.urlencode({
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        }).encode()
        req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, timeout=15) as r:
            tokens = json.loads(r.read())
        if "error" in tokens:
            raise ValueError(f"{tokens['error']}: {tokens.get('error_description', '')}")
        tokens["expires_at"] = time.time() + tokens.get("expires_in", 3600)
        return tokens

    def refresh_tokens(self, tokens: dict) -> dict:
        data = urllib.parse.urlencode({
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": tokens["refresh_token"],
            "grant_type": "refresh_token",
        }).encode()
        req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, timeout=15) as r:
            new_tokens = json.loads(r.read())
        if "error" in new_tokens:
            raise ValueError(f"{new_tokens['error']}: {new_tokens.get('error_description', '')}")
        new_tokens["expires_at"] = time.time() + new_tokens.get("expires_in", 3600)
        return new_tokens

    def get_access_token(self, tokens: dict, storage=None) -> str:
        if time.time() >= tokens.get("expires_at", 0) - 60:
            tokens = self.refresh_tokens(tokens)
            if storage:
                storage.save_microsoft_tokens(tokens)
        return tokens["access_token"]
