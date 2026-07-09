import httpx
import pytest

from finbot.core.errors import ConfigurationError
from finbot.core.settings import Settings
from finbot.telegram.client import TelegramClient


def test_send_message_calls_telegram_api() -> None:
    captured_json: dict[str, object] | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_json
        captured_json = dict(__import__("json").loads(request.content))
        assert request.url.path == "/bottest-token/sendMessage"
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://example.test")
    telegram_client = TelegramClient(
        bot_token="test-token",
        base_url="https://example.test",
        client=client,
    )

    response = telegram_client.send_message(chat_id=123, text="Lancamento registrado")

    assert response == {"ok": True, "result": {"message_id": 1}}
    assert captured_json == {"chat_id": 123, "text": "Lancamento registrado"}


def test_from_settings_requires_bot_token() -> None:
    with pytest.raises(ConfigurationError):
        TelegramClient.from_settings(Settings(telegram_bot_token=None))
