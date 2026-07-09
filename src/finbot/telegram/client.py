import httpx

from finbot.core.errors import ConfigurationError
from finbot.core.settings import Settings


class TelegramClient:
    def __init__(
        self,
        bot_token: str,
        base_url: str = "https://api.telegram.org",
        client: httpx.Client | None = None,
    ) -> None:
        self._bot_token = bot_token
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=20)

    @classmethod
    def from_settings(cls, settings: Settings) -> "TelegramClient":
        if not settings.telegram_bot_token:
            raise ConfigurationError("TELEGRAM_BOT_TOKEN is required")
        return cls(bot_token=settings.telegram_bot_token)

    def send_message(self, chat_id: int | str, text: str) -> dict[str, object]:
        response = self._client.post(
            f"{self._base_url}/bot{self._bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
        )
        response.raise_for_status()
        return dict(response.json())
