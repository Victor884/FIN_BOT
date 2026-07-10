import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from finbot.ai.groq_service import (
    GroqRateLimitError,
    GroqService,
    GroqServiceError,
    GroqUnavailableError,
)
from finbot.api.dependencies.auth import get_current_user
from finbot.api.schemas.ai import AiCompletionData, AiCompletionRequest
from finbot.api.schemas.common import ApiResponse
from finbot.db.models import UserRecord

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])
logger = logging.getLogger(__name__)


def get_groq_service(request: Request) -> GroqService | None:
    return request.app.state.groq_service


@router.post(
    "/completions",
    response_model=ApiResponse[AiCompletionData],
    summary="Gera uma resposta curta usando Groq",
)
async def create_completion(
    payload: AiCompletionRequest,
    request: Request,
    user: UserRecord = Depends(get_current_user),
    service: GroqService | None = Depends(get_groq_service),
) -> ApiResponse[AiCompletionData]:
    settings = request.app.state.settings
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A integracao com IA nao esta configurada.",
        )
    if len(payload.prompt) > settings.groq_max_prompt_chars:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"O prompt deve ter no maximo {settings.groq_max_prompt_chars} caracteres.",
        )
    if not await request.app.state.groq_rate_limiter.allow(user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas solicitacoes de IA. Aguarde um minuto e tente novamente.",
        )
    try:
        completion = await service.complete(payload.prompt, user.id)
    except GroqRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except GroqUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GroqServiceError as exc:
        logger.warning("groq_response_invalid user_id=%s error_type=%s", user.id, type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="Nao foi possivel gerar uma resposta da IA.",
        ) from exc
    return ApiResponse(
        data=AiCompletionData(**completion.__dict__),
        request_id=request.state.request_id,
    )
