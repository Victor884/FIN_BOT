from fastapi.testclient import TestClient

from finbot.api.app import create_app
from finbot.api.routes import telegram
from finbot.core.settings import Settings


def make_client(webhook_secret: str | None = None) -> TestClient:
    app = create_app(Settings(telegram_webhook_secret=webhook_secret))
    app.dependency_overrides[telegram.get_settings] = lambda: Settings(
        telegram_webhook_secret=webhook_secret
    )
    return TestClient(app)


def test_telegram_webhook_accepts_valid_update() -> None:
    client = make_client()

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

    assert response.status_code == 202
    assert response.json() == {"status": "accepted", "update_id": 123}


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
