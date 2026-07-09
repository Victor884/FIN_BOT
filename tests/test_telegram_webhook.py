from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker

from finbot.api.app import create_app
from finbot.api.routes import telegram
from finbot.core.settings import Settings
from finbot.db.base import Base
from finbot.db.repositories import CardRepository, TransactionRepository
from finbot.parser.rules import RuleBasedParser
from finbot.db.repositories import AccountRepository
from finbot.services.messages import BotMessageService
from finbot.services.transactions import TransactionEntryService


class FakeTelegramClient:
    def __init__(self) -> None:
        self.messages: list[tuple[int | str, str]] = []

    def send_message(self, chat_id: int | str, text: str) -> dict[str, object]:
        self.messages.append((chat_id, text))
        return {"ok": True}


class FakeSheetsClient:
    def __init__(self) -> None:
        self.appended_ids: list[str] = []
        self.appended_rows: list[list[object]] = []
        self.setup_calls = 0

    def append_transaction(self, transaction) -> dict[str, object]:  # type: ignore[no-untyped-def]
        self.appended_ids.append(transaction.id)
        return {"updates": {"updatedRows": 1}}

    def append_transaction_row(self, row: list[object]) -> dict[str, object]:
        self.appended_rows.append(row)
        return {"updates": {"updatedRows": 1}}

    def setup_workbook(self) -> list[dict[str, object]]:
        self.setup_calls += 1
        return [{"updatedRows": 1}]


def make_service(session: Session) -> TransactionEntryService:
    parser = RuleBasedParser(today_provider=lambda: date(2026, 7, 9))
    repository = TransactionRepository(session)
    return TransactionEntryService(repository=repository, parser=parser)


def make_bot_service(session: Session) -> BotMessageService:
    parser = RuleBasedParser(today_provider=lambda: date(2026, 7, 9))
    transaction_repository = TransactionRepository(session)
    account_repository = AccountRepository(session)
    card_repository = CardRepository(session)
    transaction_service = TransactionEntryService(
        repository=transaction_repository,
        parser=parser,
        account_repository=account_repository,
        card_repository=card_repository,
    )
    return BotMessageService(
        transaction_service=transaction_service,
        transaction_repository=transaction_repository,
        account_repository=account_repository,
        card_repository=card_repository,
    )


def make_client(
    webhook_secret: str | None = None,
    telegram_client: FakeTelegramClient | None = None,
    sheets_client: FakeSheetsClient | None = None,
) -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = session_factory()

    app = create_app(Settings(telegram_webhook_secret=webhook_secret))
    app.dependency_overrides[telegram.get_settings] = lambda: Settings(
        telegram_webhook_secret=webhook_secret
    )
    app.dependency_overrides[telegram.get_transaction_entry_service] = lambda: make_service(session)
    app.dependency_overrides[telegram.get_bot_message_service] = lambda: make_bot_service(session)
    app.dependency_overrides[telegram.get_telegram_client] = lambda: telegram_client
    app.dependency_overrides[telegram.get_google_sheets_client] = lambda: sheets_client
    return TestClient(app)


def test_telegram_webhook_records_valid_update() -> None:
    fake_telegram = FakeTelegramClient()
    fake_sheets = FakeSheetsClient()
    client = make_client(telegram_client=fake_telegram, sheets_client=fake_sheets)

    response = client.post(
        "/telegram/webhook",
        json={
            "update_id": 123,
            "message": {
                "message_id": 10,
                "date": 1783526400,
                "chat": {"id": 456, "type": "private"},
                "text": "Gastei R$ 45 no mercado hoje",
            },
        },
    )

    body = response.json()

    assert response.status_code == 202
    assert body["status"] == "recorded"
    assert body["update_id"] == 123
    assert body["transaction_ids"][0] is not None
    assert body["sheet_synced"] is True
    assert body["telegram_replied"] is True
    assert body["errors"] == []
    assert fake_sheets.appended_rows[0][0] == body["transaction_ids"][0]
    assert fake_telegram.messages == [
        (456, "Lancamento registrado: Despesa de R$ 45,00 - mercado - Categoria: alimentacao.")
    ]


def test_telegram_webhook_returns_missing_fields() -> None:
    fake_telegram = FakeTelegramClient()
    fake_sheets = FakeSheetsClient()
    client = make_client(telegram_client=fake_telegram, sheets_client=fake_sheets)

    response = client.post(
        "/telegram/webhook",
        json={
            "update_id": 123,
            "message": {
                "message_id": 10,
                "date": 1783526400,
                "chat": {"id": 456, "type": "private"},
                "text": "Gastei no mercado hoje",
            },
        },
    )

    assert response.status_code == 202
    assert response.json()["status"] == "needs_more_info"
    assert response.json()["missing_fields"] == [["amount"]]
    assert response.json()["sheet_synced"] is False
    assert response.json()["telegram_replied"] is True
    assert fake_sheets.appended_ids == []
    assert fake_telegram.messages == [
        (456, "Entendi a movimentacao, mas faltou o valor. Qual foi o valor?")
    ]


def test_telegram_webhook_export_updates_google_sheets() -> None:
    fake_telegram = FakeTelegramClient()
    fake_sheets = FakeSheetsClient()
    client = make_client(telegram_client=fake_telegram, sheets_client=fake_sheets)

    response = client.post(
        "/telegram/webhook",
        json={
            "update_id": 123,
            "message": {
                "message_id": 10,
                "date": 1783526400,
                "chat": {"id": 456, "type": "private"},
                "text": "/exportar",
            },
        },
    )

    assert response.status_code == 202
    assert response.json()["status"] == "export"
    assert response.json()["sheet_synced"] is True
    assert fake_sheets.setup_calls == 1
    assert fake_telegram.messages == [
        (
            456,
            "Vou atualizar o Google Sheets em segundo plano. Te aviso aqui quando terminar.",
        ),
        (456, "Google Sheets atualizado com abas, cabecalhos e formulas."),
    ]


def test_telegram_webhook_ignores_update_without_text() -> None:
    client = make_client()

    response = client.post(
        "/telegram/webhook",
        json={
            "update_id": 123,
            "message": {
                "message_id": 10,
                "date": 1783526400,
                "chat": {"id": 456, "type": "private"},
            },
        },
    )

    assert response.status_code == 202
    assert response.json()["status"] == "ignored"


def test_telegram_webhook_rejects_invalid_secret() -> None:
    client = make_client(webhook_secret="expected-secret")

    response = client.post("/telegram/webhook", json={"update_id": 123})

    assert response.status_code == 401


def test_telegram_webhook_accepts_valid_secret() -> None:
    client = make_client(webhook_secret="expected-secret")

    response = client.post(
        "/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "expected-secret"},
        json={"update_id": 123},
    )

    assert response.status_code == 202
