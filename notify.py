import requests

from config import REQUEST_TIMEOUT, TELEGRAM_CHAT_ID, TELEGRAM_TOKEN


def send(text):
    """Send to Telegram, or print if no bot is configured."""
    if not (TELEGRAM_TOKEN and TELEGRAM_CHAT_ID):
        print(text, "\n" + "-" * 40)
        return
    r = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "disable_web_page_preview": True},
        timeout=REQUEST_TIMEOUT,
    )
    r.raise_for_status()
