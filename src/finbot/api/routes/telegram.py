import logging
import inspect
from collections.abc import Iterator
from time import perf_counter

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool

from finbot.core.settings import Settings
from finbot.db.models import TelegramUpdateRecord
from finbot.db.repositories import AccountRepository, CardRepository, TransactionRepository, UserRepository
from finbot.db.session import create_session_factory
from finbot.sheets.client import GoogleSheetsClient
from finbot.sheets.rows import transaction_to_sheet_row
from finbot.services.messages import BotMessageService
from finbot.services.transactions import TransactionEntryService
from finbot.telegram.client import TelegramClient
from finbot.telegram.schemas import TelegramUpdate

router = APIRouter(prefix="/telegram", tags=["telegram"])
logger = logging.getLogger(__name__)


async def _send_telegram_message(
    telegram_client: TelegramClient | object, chat_id: int | str, text: str
) -> None:
    if hasattr(telegram_client, "send_message_async"):
        await telegram_client.send_message_async(chat_id=chat_id, text=text)  # type: ignore[attr-defined]
        return
    send_result = telegram_client.send_message(chat_id=chat_id, text=text)  # type: ignore[attr-defined]
    if inspect.isawaitable(send_result):
        await send_result


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_transaction_entry_service(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Iterator[TransactionEntryService]:
    session_factory = create_session_factory(settings)
    with session_factory() as session:
        try:
            repository = TransactionRepository(session)
            account_repository = AccountRepository(session)
            card_repository = CardRepository(session)
            parser = request.app.state.financial_parser
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
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Iterator[BotMessageService]:
    session_factory = create_session_factory(settings)
    with session_factory() as session:
        try:
            transaction_repository = TransactionRepository(session)
            account_repository = AccountRepository(session)
            card_repository = CardRepository(session)
            parser = request.app.state.financial_parser
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


def get_telegram_client(request: Request) -> TelegramClient | None:
    return request.app.state.telegram_client


def get_google_sheets_client(request: Request) -> GoogleSheetsClient | None:
    return request.app.state.sheets_client


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
    total_start = perf_counter()
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

    user_repository = UserRepository(service.session)
    telegram_user = update.message.from_user
    user = user_repository.get_or_create_telegram(
        telegram_user_id=telegram_user.id if telegram_user else update.message.chat.id,
        chat_id=update.message.chat.id,
        name=telegram_user.first_name if telegram_user else None,
        username=telegram_user.username if telegram_user else None,
    )
    existing_update = service.session.get(TelegramUpdateRecord, str(update.update_id))
    if existing_update is not None:
        logger.info(
            "telegram_update_duplicate update_id=%s user_id=%s", update.update_id, user.id
        )
        return {"status": "duplicate_update", "update_id": update.update_id}

    service.bind_user(user.id)
    result = await run_in_threadpool(service.handle_text, update.message.text)
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
            telegram_start = perf_counter()
            await _send_telegram_message(telegram_client, update.message.chat.id, result.message)
            telegram_duration_ms = round((perf_counter() - telegram_start) * 1000)
            telegram_replied = True
        except Exception:
            logger.exception("telegram_send_message_failed chat_id=%s", update.message.chat.id)

    if result.records and sheets_client is not None:
        rows = [transaction_to_sheet_row(record) for record in result.records]
        background_tasks.add_task(
            _sync_transaction_rows_to_sheets,
            sheets_client,
            rows,
            request.app.state.session_factory,
        )
        sheet_synced = True

    parser_duration_ms = sum(entry.parser_duration_ms for entry in result.entry_results)
    validation_duration_ms = sum(entry.validation_duration_ms for entry in result.entry_results)
    database_duration_ms = sum(entry.database_duration_ms for entry in result.entry_results)
    ai_duration_ms = sum(entry.ai_duration_ms for entry in result.entry_results)
    duplicate_blocked = any(entry.status.value == "duplicate" for entry in result.entry_results)
    total_duration_ms = round((perf_counter() - total_start) * 1000)
    service.session.add(
        TelegramUpdateRecord(
            update_id=str(update.update_id),
            user_id=user.id,
            status=result.status,
            parser_source="ai" if ai_duration_ms else "rules",
            ai_used=bool(ai_duration_ms),
            duplicate_blocked=duplicate_blocked,
            parser_duration_ms=parser_duration_ms,
            validation_duration_ms=validation_duration_ms,
            database_duration_ms=database_duration_ms,
            telegram_response_duration_ms=telegram_duration_ms if telegram_client else 0,
            total_duration_ms=total_duration_ms,
        )
    )
    logger.info(
        "telegram_processed update_id=%s user_id=%s parser_duration_ms=%s "
        "validation_duration_ms=%s database_duration_ms=%s ai_duration_ms=%s "
        "telegram_response_duration_ms=%s total_duration_ms=%s status=%s",
        update.update_id,
        user.id,
        parser_duration_ms,
        validation_duration_ms,
        database_duration_ms,
        ai_duration_ms,
        telegram_duration_ms if telegram_client else 0,
        total_duration_ms,
        result.status,
    )

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
    session_factory=None,  # type: ignore[no-untyped-def]
) -> None:
    try:
        for row in rows:
            sheets_client.append_transaction_row(row)
        if session_factory is not None:
            transaction_ids = [str(row[0]) for row in rows]
            with session_factory() as session:
                from sqlalchemy import update

                from finbot.db.models import TransactionRecord

                session.execute(
                    update(TransactionRecord)
                    .where(TransactionRecord.id.in_(transaction_ids))
                    .values(sheets_synced=True)
                )
                session.commit()
    except Exception:
        logger.exception("google_sheets_sync_failed rows=%s", len(rows))


async def _setup_sheets_and_notify(
    sheets_client: GoogleSheetsClient,
    telegram_client: TelegramClient | None,
    chat_id: int | str,
) -> None:
    try:
        await run_in_threadpool(sheets_client.setup_workbook)
    except Exception:
        logger.exception("google_sheets_export_failed")
        if telegram_client is not None:
            try:
                await _send_telegram_message(
                    telegram_client,
                    chat_id,
                    "Nao consegui atualizar o Google Sheets agora. Verifique as credenciais.",
                )
            except Exception:
                logger.exception("telegram_export_failure_notification_failed chat_id=%s", chat_id)
        return

    if telegram_client is not None:
        try:
            await _send_telegram_message(
                telegram_client,
                chat_id,
                "Google Sheets atualizado com abas, cabecalhos e formulas.",
            )
        except Exception:
            logger.exception("telegram_export_success_notification_failed chat_id=%s", chat_id)
