from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from finbot.core.settings import Settings
from finbot.telegram.schemas import TelegramUpdate

router = APIRouter(prefix="/telegram", tags=["telegram"])


def get_settings() -> Settings:
    return Settings()


@router.post("/webhook", status_code=status.HTTP_202_ACCEPTED)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> dict[str, str | int | None]:
    if settings.telegram_webhook_secret:
        if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Telegram webhook secret",
            )

    payload = await request.json()
    update = TelegramUpdate.model_validate(payload)

    return {"status": "accepted", "update_id": update.update_id}

