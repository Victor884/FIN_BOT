from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from finbot.api.errors import register_error_handlers
from finbot.api.middleware import register_request_logging
from finbot.api.routes.health import router as health_router
from finbot.api.routes.auth import router as auth_router
from finbot.api.routes.ai import router as ai_router
from finbot.api.routes.admin_dashboard import router as admin_dashboard_router
from finbot.api.routes.user_dashboard import router as user_dashboard_router
from finbot.api.routes.telegram import router as telegram_router
from finbot.core.logging import configure_logging
from finbot.core.settings import Settings
from finbot.db.session import create_database_schema, create_session_factory
from finbot.sheets.client import GoogleSheetsClient
from finbot.telegram.client import TelegramClient
from finbot.ai.groq_service import GroqService
from finbot.services.rate_limit import InMemoryRateLimiter
from finbot.parser.factory import build_financial_parser
from finbot.core.errors import ConfigurationError


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or Settings()
    if app_settings.app_env == "production":
        if len(app_settings.jwt_secret) < 32 or app_settings.jwt_secret == "change-me-in-production":
            raise ConfigurationError("JWT_SECRET must be configured in production")
        if "*" in app_settings.csv_values("cors_allowed_origins"):
            raise ConfigurationError("Wildcard CORS is not allowed in production")
    configure_logging(app_settings.log_level)
    if app_settings.database_auto_migrate:
        create_database_schema(app_settings)
    @asynccontextmanager
    async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
        yield
        if app.state.telegram_client is not None:
            await app.state.telegram_client.close()
        if app.state.groq_service is not None:
            await app.state.groq_service.close()

    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        debug=app_settings.app_debug,
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.state.session_factory = create_session_factory(app_settings)
    app.state.financial_parser = build_financial_parser(app_settings)
    app.state.groq_service = GroqService.from_settings(app_settings)
    app.state.groq_rate_limiter = InMemoryRateLimiter(app_settings.groq_requests_per_minute)
    app.state.telegram_client = (
        TelegramClient.from_settings(app_settings) if app_settings.telegram_bot_token else None
    )
    app.state.sheets_client = (
        GoogleSheetsClient.from_settings(app_settings)
        if app_settings.google_sheets_active
        else None
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.csv_values("cors_allowed_origins"),
        allow_origin_regex=app_settings.cors_allowed_origin_regex,
        allow_credentials=app_settings.cors_allow_credentials,
        allow_methods=app_settings.csv_values("cors_allowed_methods"),
        allow_headers=app_settings.csv_values("cors_allowed_headers"),
    )

    register_request_logging(app)
    register_error_handlers(app)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(ai_router)
    app.include_router(admin_dashboard_router)
    app.include_router(user_dashboard_router)
    app.include_router(telegram_router)
    return app


app = create_app()
