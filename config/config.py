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

  ROLE_PASSWORD_OPERATIONS_DIRECTOR  – Web auth password for operations_director
  ROLE_PASSWORD_ACCOUNTING           – Web auth password for accounting
  ROLE_PASSWORD_ADMIN                – Web auth password for admin

  PASSWORD_MANAGER_EKATERINA – Web-mode password for manager Екатерина
  ID_MANAGER_EKATERINA       – Manager ID (managers table PK) for Екатерина
  PASSWORD_MANAGER_YULIA     – Web-mode password for manager Юлия
  ID_MANAGER_YULIA           – Manager ID (managers table PK) for Юлия

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

    # Role passwords for web (browser) auth — role-login endpoint
    role_password_operations_director: str = ""
    role_password_accounting: str = ""
    role_password_admin: str = ""

    # Manager-specific credentials for web (browser) auth
    password_manager_ekaterina: str = ""
    id_manager_ekaterina: str = ""
    password_manager_yulia: str = ""
    id_manager_yulia: str = ""

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
      - DATABASE_URL

    Optional variables (warnings only — bot polling is gated by RUN_BOT flag):
      - TELEGRAM_BOT_TOKEN  (required only when RUN_BOT=true)
      - WEBAPP_URL
      - API_BASE_URL (frontend fallback to same-origin if not set)
    """
    import logging
    import os
    _logger = logging.getLogger(__name__)

    if not settings.database_url:
        raise RuntimeError(
            "Missing required environment variable: DATABASE_URL. "
            "Set it in your environment or in a .env file."
        )

    run_bot = os.getenv("RUN_BOT", "false").lower() == "true"
    if run_bot and not settings.telegram_bot_token:
        raise RuntimeError(
            "Missing required environment variable: TELEGRAM_BOT_TOKEN "
            "(required when RUN_BOT=true). "
            "Set it in your environment or in a .env file."
        )

    if not settings.telegram_bot_token:
        _logger.warning(
            "TELEGRAM_BOT_TOKEN is not set. "
            "Telegram bot polling will be disabled unless RUN_BOT=true is also set."
        )
    if not settings.webapp_url:
        _logger.warning(
            "WEBAPP_URL is not set. Mini App deep-links will not work correctly."
        )
