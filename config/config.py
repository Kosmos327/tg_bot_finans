"""
Central configuration loaded from environment variables.

Required environment variables (validated at startup via validate_settings()):
  TELEGRAM_BOT_TOKEN  - Telegram bot token from @BotFather
  WEBAPP_URL          - Public HTTPS URL of the Mini App
  DATABASE_URL        - PostgreSQL connection string
                        e.g. postgresql://user:password@host:5432/database

Optional environment variables:
  API_BASE_URL        - Public URL of the backend API
                        (frontend falls back to same-origin if not set)

For local development, copy .env.example to .env and fill in the values.
Production deployments should inject variables directly; no .env file is needed.
"""

from dotenv import load_dotenv

# Load .env only if it exists; never fail when running in production without it
load_dotenv(override=False)

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    telegram_bot_token: str = ""
    webapp_url: str = ""
    database_url: str = ""
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
      - DATABASE_URL

    Optional variables:
      - API_BASE_URL (frontend fallback to same-origin if not set)
    """
    missing = []
    if not settings.telegram_bot_token:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not settings.webapp_url:
        missing.append("WEBAPP_URL")
    if not settings.database_url:
        missing.append("DATABASE_URL")
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Set them in your environment or in a .env file."
        )
