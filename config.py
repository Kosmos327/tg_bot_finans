"""Central configuration loaded from environment variables / .env file."""

import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# Database
DATABASE_URL: str = os.environ.get("DATABASE_URL", "")

# Deal settings
DEAL_ID_PREFIX: str = os.environ.get("DEAL_ID_PREFIX", "DEAL-")
# PostgreSQL column names used for required-field validation
REQUIRED_DEAL_FIELDS: list[str] = [
    field.strip()
    for field in os.environ.get(
        "REQUIRED_DEAL_FIELDS", "deal_name,client_id,amount_with_vat"
    ).split(",")
]
