from collections.abc import Iterator

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from finbot.core.settings import Settings
from finbot.db.repositories import TransactionRepository
from finbot.db.session import create_database_schema, create_session_factory
from finbot.parser.factory import build_financial_parser
from finbot.services.transactions import TransactionEntryService
from finbot.telegram.schemas import TelegramUpdate

router = APIRouter(prefix="/telegram", tags=["telegram"])


def get_settings() -> Settings:
    return Settings()


def get_transaction_entry_service(
    settings: Settings = Depends(get_settings),
) -> Iterator[TransactionEntryService]:
    create_database_schema(settings)
    session_factory = create_session_factory(settings)
    with session_factory() as session:
        try:
            repository = TransactionRepository(session)
            parser = build_financial_parser(settings)
            yield TransactionEntryService(repository=repository, parser=parser)
            session.commit()
        except Exception:
            session.rollback()
            raise


@router.post("/webhook", status_code=status.HTTP_202_ACCEPTED)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    service: TransactionEntryService = Depends(get_transaction_entry_service),
) -> dict[str, object]:
    if settings.telegram_webhook_secret:
        if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Telegram webhook secret",
            )

    payload = await request.json()
    update = TelegramUpdate.model_validate(payload)

    if update.message is None or not update.message.text:
        return {"status": "ignored", "update_id": update.update_id, "reason": "message_text_missing"}

    result = service.record_from_text(update.message.text)

    return {
        "status": result.status.value,
        "update_id": update.update_id,
        "message": result.message,
        "transaction_id": result.transaction_id,
        "missing_fields": list(result.missing_fields),
        "errors": list(result.validation.errors) if result.validation else [],
        "warnings": list(result.validation.warnings) if result.validation else [],
    }
