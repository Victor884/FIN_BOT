from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    app_name: str = "finbot"
    app_debug: bool = False
    database_url: str = "sqlite:///./data/finbot.sqlite3"
    telegram_bot_token: str | None = None
    telegram_webhook_secret: str | None = None
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.4-nano"
    ai_provider: str = "openai"
    ai_enabled: bool = False
    google_sheets_spreadsheet_id: str | None = None
    google_service_account_file: str | None = None
    log_level: str = "INFO"

