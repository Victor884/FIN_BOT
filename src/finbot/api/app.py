from fastapi import FastAPI

from finbot.api.routes.health import router as health_router
from finbot.core.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or Settings()
    app = FastAPI(title=app_settings.app_name, debug=app_settings.app_debug)
    app.include_router(health_router)
    return app


app = create_app()

