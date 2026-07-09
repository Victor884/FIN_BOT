import logging
from collections.abc import Iterator

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status

from finbot.core.settings import Settings
from finbot.db.repositories import AccountRepository, CardRepository, TransactionRepository
from finbot.db.session import create_database_schema, create_session_factory
from finbot.parser.factory import build_financial_parser
from finbot.sheets.client import GoogleSheetsClient
from finbot.sheets.rows import transaction_to_sheet_row
from finbot.services.messages import BotMessageService
from finbot.services.transactions import TransactionEntryService
from finbot.telegram.client import TelegramClient
from finbot.telegram.schemas import TelegramUpdate

router = APIRouter(prefix="/telegram", tags=["telegram"])
logger = logging.getLogger(__name__)


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
            account_repository = AccountRepository(session)
            card_repository = CardRepository(session)
            parser = build_financial_parser(settings)
            yield TransactionEntryService(
                repository=repository,
                parser=parser,
                account_repository=account_repository,
                card_repository=card_repository,
            )
            session.commit()
        except Exception:
            session.rollback()
            raise


def get_bot_message_service(
    settings: Settings = Depends(get_settings),
) -> Iterator[BotMessageService]:
    create_database_schema(settings)
    session_factory = create_session_factory(settings)
    with session_factory() as session:
        try:
            transaction_repository = TransactionRepository(session)
            account_repository = AccountRepository(session)
            card_repository = CardRepository(session)
            parser = build_financial_parser(settings)
            transaction_service = TransactionEntryService(
                repository=transaction_repository,
                parser=parser,
                account_repository=account_repository,
                card_repository=card_repository,
            )
            yield BotMessageService(
                transaction_service=transaction_service,
                transaction_repository=transaction_repository,
                account_repository=account_repository,
                card_repository=card_repository,
            )
            session.commit()
        except Exception:
            session.rollback()
            raise


def get_telegram_client(settings: Settings = Depends(get_settings)) -> TelegramClient | None:
    if not settings.telegram_bot_token:
        return None
    return TelegramClient.from_settings(settings)


def get_google_sheets_client(settings: Settings = Depends(get_settings)) -> GoogleSheetsClient | None:
    if not settings.google_sheets_spreadsheet_id or not settings.google_service_account_file:
        return None
    return GoogleSheetsClient.from_settings(settings)


@router.post("/webhook", status_code=status.HTTP_202_ACCEPTED)
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    service: BotMessageService = Depends(get_bot_message_service),
    telegram_client: TelegramClient | None = Depends(get_telegram_client),
    sheets_client: GoogleSheetsClient | None = Depends(get_google_sheets_client),
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

    result = service.handle_text(update.message.text)
    sheet_synced = False
    telegram_replied = False

    if result.status == "export":
        if sheets_client is not None:
            result = type(result)(
                status=result.status,
                message=(
                    "Vou atualizar o Google Sheets em segundo plano. "
                    "Te aviso aqui quando terminar."
                ),
                records=result.records,
                entry_results=result.entry_results,
            )
            sheet_synced = True
            background_tasks.add_task(
                _setup_sheets_and_notify,
                sheets_client,
                telegram_client,
                update.message.chat.id,
            )
        else:
            result = type(result)(
                status=result.status,
                message="Google Sheets nao esta configurado neste ambiente.",
                records=result.records,
                entry_results=result.entry_results,
            )

    if telegram_client is not None:
        try:
            telegram_client.send_message(chat_id=update.message.chat.id, text=result.message)
            telegram_replied = True
        except Exception:
            logger.exception("telegram_send_message_failed chat_id=%s", update.message.chat.id)

    if result.records and sheets_client is not None:
        rows = [transaction_to_sheet_row(record) for record in result.records]
        background_tasks.add_task(_sync_transaction_rows_to_sheets, sheets_client, rows)
        sheet_synced = True

    return {
        "status": result.status,
        "update_id": update.update_id,
        "message": result.message,
        "transaction_ids": [record.id for record in result.records],
        "sheet_synced": sheet_synced,
        "telegram_replied": telegram_replied,
        "entry_statuses": [entry.status.value for entry in result.entry_results],
        "missing_fields": [
            list(entry.missing_fields) for entry in result.entry_results if entry.missing_fields
        ],
        "errors": [
            list(entry.validation.errors)
            for entry in result.entry_results
            if entry.validation and entry.validation.errors
        ],
        "warnings": [
            list(entry.validation.warnings)
            for entry in result.entry_results
            if entry.validation and entry.validation.warnings
        ],
    }


def _sync_transaction_rows_to_sheets(
    sheets_client: GoogleSheetsClient,
    rows: list[list[object]],
) -> None:
    try:
        for row in rows:
            sheets_client.append_transaction_row(row)
    except Exception:
        logger.exception("google_sheets_sync_failed rows=%s", len(rows))


def _setup_sheets_and_notify(
    sheets_client: GoogleSheetsClient,
    telegram_client: TelegramClient | None,
    chat_id: int | str,
) -> None:
    try:
        sheets_client.setup_workbook()
    except Exception:
        logger.exception("google_sheets_export_failed")
        if telegram_client is not None:
            try:
                telegram_client.send_message(
                    chat_id=chat_id,
                    text="Nao consegui atualizar o Google Sheets agora. Verifique as credenciais.",
                )
            except Exception:
                logger.exception("telegram_export_failure_notification_failed chat_id=%s", chat_id)
        return

    if telegram_client is not None:
        try:
            telegram_client.send_message(
                chat_id=chat_id,
                text="Google Sheets atualizado com abas, cabecalhos e formulas.",
            )
        except Exception:
            logger.exception("telegram_export_success_notification_failed chat_id=%s", chat_id)
