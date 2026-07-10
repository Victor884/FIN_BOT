import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from finbot.core.errors import ConfigurationError, FinbotError


logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "unexpected_error request_id=%s path=%s error_type=%s",
            getattr(request.state, "request_id", "unknown"),
            request.url.path,
            type(exc).__name__,
        )
        if request.url.path.startswith("/api/v1"):
            return _api_error_response(
                request,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Nao foi possivel processar a solicitacao.",
            )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "internal_error", "message": "Internal server error."},
        )

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if not request.url.path.startswith("/api/v1"):
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        return _api_error_response(
            request,
            exc.status_code,
            _error_code(exc.status_code),
            _friendly_message(exc.status_code, str(exc.detail)),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        if not request.url.path.startswith("/api/v1"):
            return JSONResponse(status_code=422, content={"detail": exc.errors()})
        details = [
            {"field": ".".join(str(part) for part in error["loc"]), "type": error["type"]}
            for error in exc.errors()
        ]
        return _api_error_response(
            request,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "VALIDATION_ERROR",
            "Revise os dados enviados.",
            details,
        )

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


def _api_error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: list[object] | None = None,
) -> JSONResponse:
    from datetime import UTC, datetime

    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "data": None,
            "message": message,
            "error": {"code": code, "details": details or []},
            "request_id": getattr(request.state, "request_id", "unknown"),
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )


def _error_code(status_code: int) -> str:
    return {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
    }.get(status_code, "INTERNAL_ERROR")


def _friendly_message(status_code: int, detail: str) -> str:
    if status_code in {400, 404, 409, 422} and detail:
        return detail
    return {
        401: "Sua sessao expirou ou nao e valida.",
        403: "Voce nao tem permissao para acessar este recurso.",
        429: "Muitas solicitacoes. Tente novamente em instantes.",
        502: "A integracao externa retornou uma resposta invalida.",
        503: "O servico esta temporariamente indisponivel.",
    }.get(status_code, "Nao foi possivel processar a solicitacao.")
