from fastapi import FastAPI

from finbot.api.errors import register_error_handlers
from finbot.api.middleware import register_request_logging
from finbot.api.routes.health import router as health_router
from finbot.api.routes.telegram import router as telegram_router
from finbot.core.logging import configure_logging
from finbot.core.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or Settings()
    configure_logging(app_settings.log_level)
    app = FastAPI(title=app_settings.app_name, debug=app_settings.app_debug)
    register_request_logging(app)
    register_error_handlers(app)
    app.include_router(health_router)
    app.include_router(telegram_router)
    return app


app = create_app()
