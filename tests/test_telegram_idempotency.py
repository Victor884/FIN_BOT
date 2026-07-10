from fastapi.testclient import TestClient

from finbot.api.app import create_app
from finbot.api.routes import telegram
from finbot.core.settings import Settings


class FakeTelegramClient:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def send_message(self, chat_id: int | str, text: str) -> dict[str, object]:
        self.messages.append(text)
        return {"ok": True}


def test_duplicate_telegram_update_is_processed_once(tmp_path) -> None:  # type: ignore[no-untyped-def]
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'idempotency.db'}",
        telegram_bot_token=None,
        telegram_webhook_secret=None,
        google_sheets_spreadsheet_id=None,
        google_service_account_file=None,
    )
    app = create_app(settings)
    fake = FakeTelegramClient()
    app.dependency_overrides[telegram.get_telegram_client] = lambda: fake
    app.dependency_overrides[telegram.get_google_sheets_client] = lambda: None
    client = TestClient(app)
    payload = {
        "update_id": 98765,
        "message": {
            "message_id": 1,
            "date": 1783526400,
            "chat": {"id": 456, "type": "private"},
            "from": {"id": 456, "first_name": "Teste", "is_bot": False},
            "text": "Gastei R$ 45 no mercado hoje",
        },
    }

    first = client.post("/telegram/webhook", json=payload)
    second = client.post("/telegram/webhook", json=payload)

    assert first.status_code == 202
    assert first.json()["status"] == "recorded"
    assert second.status_code == 202
    assert second.json()["status"] == "duplicate_update"
    assert len(fake.messages) == 1
