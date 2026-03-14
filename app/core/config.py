"""
Central configuration loaded from environment variables.

Required:
  DATABASE_URL – PostgreSQL connection string
                 e.g. postgresql+asyncpg://user:password@host:5432/database

Optional:
  TELEGRAM_BOT_TOKEN – Telegram bot token
  WEBAPP_URL          – Public HTTPS URL of the Mini App
  ROLE_PASSWORD_MANAGER              – Password for 'manager' role login
  ROLE_PASSWORD_OPERATIONS_DIRECTOR  – Password for 'operations_director' role login
  ROLE_PASSWORD_ACCOUNTING           – Password for 'accounting' role login
  ROLE_PASSWORD_ADMIN                – Password for 'admin' role login
"""

import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv(override=False)


class Settings(BaseSettings):
    database_url: str = os.getenv("DATABASE_URL", "")
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    webapp_url: str = os.getenv("WEBAPP_URL", "")
    api_base_url: str = os.getenv("API_BASE_URL", "")

    # Role passwords for Mini App login
    role_password_manager: str = os.getenv("ROLE_PASSWORD_MANAGER", "")
    role_password_operations_director: str = os.getenv("ROLE_PASSWORD_OPERATIONS_DIRECTOR", "")
    role_password_accounting: str = os.getenv("ROLE_PASSWORD_ACCOUNTING", "")
    role_password_admin: str = os.getenv("ROLE_PASSWORD_ADMIN", "")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
