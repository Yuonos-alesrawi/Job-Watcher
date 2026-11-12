import json
import logging
import os
from pathlib import Path

BASE = Path(__file__).parent

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DB_PATH = os.getenv("JOBS_DB", str(BASE / "seen.db"))
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
CHECK_EVERY_SECONDS = int(os.getenv("CHECK_EVERY_SECONDS", "3600"))
MAX_ALERTS_PER_RUN = int(os.getenv("MAX_ALERTS_PER_RUN", "20"))
REQUIRE_JUNIOR_SIGNAL = os.getenv("REQUIRE_JUNIOR_SIGNAL", "1") != "0"  # alert only if the posting says junior/entry-level
REQUEST_TIMEOUT = 20
PAUSE_BETWEEN_COMPANIES = 1.0  # seconds, be polite to the public APIs
USER_AGENT = "job-watcher/0.1 (personal job search)"


COMPANIES_FILE = os.getenv("COMPANIES_FILE", str(BASE / "companies.json"))
REQUIRE_JUNIOR_SIGNAL = os.getenv("REQUIRE_JUNIOR_SIGNAL", "1").lower() not in ("0", "false", "no")

_last_good = []


def load_companies():
    """Read the list on every run; a broken edit keeps the last good list instead of crashing."""
    global _last_good
    try:
        with open(COMPANIES_FILE, encoding="utf-8") as f:
            raw = json.load(f)
        _last_good = [
            {"source": c["source"].strip().lower(), "name": c["name"].strip().lower()} for c in raw
        ]
    except (OSError, ValueError, KeyError, AttributeError) as exc:
        logging.getLogger("config").error(
            "cannot read %s (%s); using last good list (%d companies)",
            COMPANIES_FILE, exc, len(_last_good),
        )
    return _last_good
