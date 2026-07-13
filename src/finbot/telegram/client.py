import httpx

from finbot.core.errors import ConfigurationError
from finbot.core.settings import Settings


class TelegramClient:
    def __init__(
        self,
        bot_token: str,
        base_url: str = "https://api.telegram.org",
        client: httpx.Client | httpx.AsyncClient | None = None,
        timeout: httpx.Timeout | None = None,
    ) -> None:
        self._bot_token = bot_token
        self._base_url = base_url.rstrip("/")
        self._async_client = client if isinstance(client, httpx.AsyncClient) else httpx.AsyncClient(
            timeout=timeout or httpx.Timeout(8.0, connect=3.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
        self._sync_client = client if isinstance(client, httpx.Client) else None

    @classmethod
    def from_settings(cls, settings: Settings) -> "TelegramClient":
        if not settings.telegram_bot_token:
            raise ConfigurationError("TELEGRAM_BOT_TOKEN is required")
        return cls(
            bot_token=settings.telegram_bot_token,
            timeout=httpx.Timeout(
                settings.http_read_timeout_seconds,
                connect=settings.http_connect_timeout_seconds,
            ),
        )

    def send_message(self, chat_id: int | str, text: str) -> dict[str, object]:
        if self._sync_client is None:
            self._sync_client = httpx.Client(timeout=httpx.Timeout(8.0, connect=3.0))
        response = self._sync_client.post(
            f"{self._base_url}/bot{self._bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
        )
        response.raise_for_status()
        return dict(response.json())

    async def send_message_async(self, chat_id: int | str, text: str) -> dict[str, object]:
        response = await self._async_client.post(
            f"{self._base_url}/bot{self._bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
        )
        response.raise_for_status()
        return dict(response.json())

    async def send_document_async(
        self, chat_id: int | str, content: bytes, filename: str, caption: str | None = None
    ) -> dict[str, object]:
        data: dict[str, str] = {"chat_id": str(chat_id)}
        if caption:
            data["caption"] = caption
        response = await self._async_client.post(
            f"{self._base_url}/bot{self._bot_token}/sendDocument",
            data=data,
            files={"document": (filename, content, "text/csv")},
        )
        response.raise_for_status()
        return dict(response.json())

    async def close(self) -> None:
        await self._async_client.aclose()
        if self._sync_client is not None:
            self._sync_client.close()
