import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from finbot.core.errors import ConfigurationError, FinbotError


logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ConfigurationError)
    async def configuration_error_handler(
        request: Request, exc: ConfigurationError
    ) -> JSONResponse:
        logger.error("configuration_error path=%s error=%s", request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "configuration_error", "message": "Application is not configured."},
        )

    @app.exception_handler(FinbotError)
    async def finbot_error_handler(request: Request, exc: FinbotError) -> JSONResponse:
        logger.warning("finbot_error path=%s error=%s", request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "finbot_error", "message": "Could not process the request."},
        )
