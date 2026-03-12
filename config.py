"""Central configuration loaded from environment variables / .env file."""

import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
BOT_TOKEN: str = os.environ["BOT_TOKEN"]

# Google Sheets
SPREADSHEET_ID: str = os.environ["SPREADSHEET_ID"]
GOOGLE_CREDENTIALS_FILE: str = os.environ.get(
    "GOOGLE_CREDENTIALS_FILE", "credentials.json"
)

# Sheet names
DEALS_SHEET: str = os.environ.get("DEALS_SHEET", "Сделки")
JOURNAL_SHEET: str = os.environ.get("JOURNAL_SHEET", "Журнал действий")

# Deal settings
DEAL_ID_PREFIX: str = os.environ.get("DEAL_ID_PREFIX", "DEAL-")
REQUIRED_DEAL_FIELDS: list[str] = [
    field.strip()
    for field in os.environ.get(
        "REQUIRED_DEAL_FIELDS", "Название,Клиент,Сумма"
    ).split(",")
]
