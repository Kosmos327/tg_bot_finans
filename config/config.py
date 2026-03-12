"""
Central configuration loaded from environment variables.

Required environment variables (validated at startup via validate_settings()):
  TELEGRAM_BOT_TOKEN          – Telegram bot token from @BotFather
  WEBAPP_URL                  – Public HTTPS URL of the Mini App
  GOOGLE_SERVICE_ACCOUNT_JSON – Full JSON content of the service account key
  GOOGLE_SHEETS_SPREADSHEET_ID – Google Spreadsheet ID

Optional environment variables:
  API_BASE_URL                – Public URL of the backend API
                                (frontend falls back to same-origin if not set)

For local development, copy .env.example to .env and fill in the values.
Production deployments should inject variables directly; no .env file is needed.
"""

import sys
from dotenv import load_dotenv

# Load .env only if it exists; never fail when running in production without it
load_dotenv(override=False)

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    telegram_bot_token: str = ""
    webapp_url: str = ""
    google_service_account_json: str = ""
    google_sheets_spreadsheet_id: str = ""
    api_base_url: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()


def validate_settings() -> None:
    """
    Validate that all required environment variables are set.

    Call this function during application startup (e.g. in main.py or bot.py)
    to fail fast with a clear error message if any required variable is missing.

    Required variables:
      - TELEGRAM_BOT_TOKEN
      - WEBAPP_URL
      - GOOGLE_SERVICE_ACCOUNT_JSON
      - GOOGLE_SHEETS_SPREADSHEET_ID

    Optional variables:
      - API_BASE_URL (frontend fallback to same-origin if not set)
    """
    missing = []
    if not settings.telegram_bot_token:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not settings.webapp_url:
        missing.append("WEBAPP_URL")
    if not settings.google_service_account_json:
        missing.append("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not settings.google_sheets_spreadsheet_id:
        missing.append("GOOGLE_SHEETS_SPREADSHEET_ID")
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Set them in your environment or in a .env file."
        )
