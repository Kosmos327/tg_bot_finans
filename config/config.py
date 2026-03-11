from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Telegram
    bot_token: str
    mini_app_url: str

    # Backend
    backend_url: str = "http://localhost:8000"
    secret_key: str = Field(default=..., description="Secret key for signing — must be set in .env")

    # Google Sheets
    google_credentials_file: str = "credentials.json"
    spreadsheet_name: str = "Финанс.xlsx"


settings = Settings()
