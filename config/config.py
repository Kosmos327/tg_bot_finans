from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    telegram_bot_token: str = ""
    webapp_url: str = ""
    google_service_account_file: str = "service_account.json"
    google_sheets_spreadsheet_id: str = ""
    api_base_url: str = "http://localhost:8000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
