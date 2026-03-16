import os

class Config:
    telegram_token: str
    data_dir: str
    def __init__(self):
        missing = [k for k in ("TELEGRAM_TOKEN",) if not os.getenv(k)]
        if missing:
            raise ValueError(f"Missing required env vars: {', '.join(missing)}")
        self.telegram_token = os.environ["TELEGRAM_TOKEN"]
        self.data_dir = os.getenv("DATA_DIR", "/data")
