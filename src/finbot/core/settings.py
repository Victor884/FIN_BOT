from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    app_name: str = "finbot"
    app_debug: bool = False
    app_version: str = "0.2.0"
    database_url: str = "sqlite:///./data/finbot.sqlite3"
    telegram_bot_token: str | None = None
    telegram_webhook_secret: str | None = None
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.4-nano"
    openai_base_url: str = "https://api.openai.com/v1"
    ai_provider: str = "openai"
    ai_enabled: bool = False
    google_sheets_enabled: bool = False
    google_sheets_spreadsheet_id: str | None = None
    google_service_account_file: str | None = None
    transaction_confirmation_threshold: float = 0.75
    database_auto_migrate: bool = True
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_backup_bucket: str | None = None
    log_level: str = "INFO"
    cors_allowed_origins: str = "http://localhost:5173"
    cors_allowed_origin_regex: str | None = None
    cors_allowed_methods: str = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    cors_allowed_headers: str = "Authorization,Content-Type,X-Request-ID"
    cors_allow_credentials: bool = True
    http_connect_timeout_seconds: float = 3.0
    http_read_timeout_seconds: float = 8.0
    jwt_secret: str = "change-me-in-production"
    jwt_access_minutes: int = 15
    jwt_refresh_days: int = 30
    auth_allow_registration: bool = False
    admin_email: str | None = None
    admin_password: str | None = None
    public_api_url: str | None = None
    metrics_retention_days: int = 90
    groq_api_key: str | None = None
    groq_model: str = "llama-3.1-8b-instant"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_timeout_seconds: float = 8.0
    groq_max_prompt_chars: int = 4000
    groq_max_output_tokens: int = 300
    groq_requests_per_minute: int = 10

    @property
    def google_sheets_configured(self) -> bool:
        return bool(self.google_sheets_spreadsheet_id and self.google_service_account_file)

    @property
    def google_sheets_active(self) -> bool:
        return self.google_sheets_enabled and self.google_sheets_configured

    def csv_values(self, field_name: str) -> list[str]:
        value = getattr(self, field_name)
        return [item.strip() for item in value.split(",") if item.strip()]
