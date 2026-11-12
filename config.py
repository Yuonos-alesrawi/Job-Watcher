import json
import os
from pathlib import Path

BASE = Path(__file__).parent

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DB_PATH = os.getenv("JOBS_DB", str(BASE / "seen.db"))
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
CHECK_EVERY_SECONDS = int(os.getenv("CHECK_EVERY_SECONDS", "3600"))
MAX_ALERTS_PER_RUN = int(os.getenv("MAX_ALERTS_PER_RUN", "20"))
REQUEST_TIMEOUT = 20
PAUSE_BETWEEN_COMPANIES = 1.0  # seconds, be polite to the public APIs
USER_AGENT = "job-watcher/0.1 (personal job search)"
COMPANIES_FILE = os.getenv("COMPANIES_FILE", str(BASE / "companies.json"))

def load_companies():
    with open(COMPANIES_FILE, encoding="utf-8") as f:
        return json.load(f)
