from fastapi import APIRouter, Request
from sqlalchemy import text

from finbot.api.schemas.common import ApiResponse
from finbot.api.schemas.dashboard import PublicConfig

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "healthy"}


@router.get("/health/ready")
def readiness(request: Request) -> dict[str, str]:
    database = "unavailable"
    try:
        with request.app.state.session_factory() as session:
            session.execute(text("SELECT 1"))
        database = "available"
    except Exception:
        pass
    status = "healthy" if database == "available" else "degraded"
    return {
        "status": status,
        "database": database,
        "version": request.app.state.settings.app_version,
    }


@router.get("/api/v1/config/public", response_model=ApiResponse[PublicConfig])
def public_config(request: Request) -> ApiResponse[PublicConfig]:
    settings = request.app.state.settings
    return ApiResponse(
        data=PublicConfig(
            api_version=settings.app_version,
            environment=settings.app_env,
            registration_enabled=settings.auth_allow_registration,
            features={
                "telegram": bool(settings.telegram_bot_token),
                "google_sheets": settings.google_sheets_active,
                "ai": settings.ai_enabled,
                "groq": bool(settings.groq_api_key),
            },
        ),
        request_id=request.state.request_id,
    )
