import os
from typing import Optional

class Config:
    telegram_token: str
    anthropic_api_key: str
    data_dir: str
    google_client_id: Optional[str]
    google_client_secret: Optional[str]

    def __init__(self):
        missing = [k for k in ("TELEGRAM_TOKEN", "ANTHROPIC_API_KEY") if not os.getenv(k)]
        if missing:
            raise ValueError(f"Missing required env vars: {', '.join(missing)}")
        self.telegram_token = os.environ["TELEGRAM_TOKEN"]
        self.anthropic_api_key = os.environ["ANTHROPIC_API_KEY"]
        self.data_dir = os.getenv("DATA_DIR", "/data")
        self.google_client_id = os.getenv("GOOGLE_CLIENT_ID") or None
        self.google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET") or None
