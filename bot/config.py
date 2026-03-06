import os
from typing import Optional

class Config:
    telegram_token: str
    data_dir: str
    google_client_id: Optional[str]
    google_client_secret: Optional[str]

    def __init__(self):
        missing = [k for k in ("TELEGRAM_TOKEN",) if not os.getenv(k)]
        if missing:
            raise ValueError(f"Missing required env vars: {', '.join(missing)}")
        self.telegram_token = os.environ["TELEGRAM_TOKEN"]
        self.data_dir = os.getenv("DATA_DIR", "/data")
        self.google_client_id = os.getenv("GOOGLE_CLIENT_ID") or None
        self.google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET") or None
        self.microsoft_client_id = os.getenv("MICROSOFT_CLIENT_ID") or None
        self.microsoft_client_secret = os.getenv("MICROSOFT_CLIENT_SECRET") or None
