import os
from dataclasses import dataclass

@dataclass
class Config:
    telegram_token: str
    anthropic_api_key: str
    data_dir: str
    google_client_id: str
    google_client_secret: str

    def __init__(self):
        missing = []
        for key in ("TELEGRAM_TOKEN", "ANTHROPIC_API_KEY"):
            if not os.getenv(key):
                missing.append(key)
        if missing:
            raise ValueError(f"Missing required env vars: {', '.join(missing)}")
        self.telegram_token = os.environ["TELEGRAM_TOKEN"]
        self.anthropic_api_key = os.environ["ANTHROPIC_API_KEY"]
        self.data_dir = os.getenv("DATA_DIR", "/data")
        self.google_client_id = os.getenv("GOOGLE_CLIENT_ID", "")
        self.google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
