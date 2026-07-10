import logging
from dataclasses import dataclass
from time import perf_counter
from typing import Any

import httpx

from finbot.core.settings import Settings

logger = logging.getLogger(__name__)


class GroqServiceError(RuntimeError):
    pass


class GroqRateLimitError(GroqServiceError):
    pass


class GroqUnavailableError(GroqServiceError):
    pass


@dataclass(frozen=True)
class GroqCompletion:
    text: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class GroqService:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: float,
        max_output_tokens: int,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._max_output_tokens = max_output_tokens
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 3.0)),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> "GroqService | None":
        if not settings.groq_api_key:
            return None
        return cls(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            base_url=settings.groq_base_url,
            timeout_seconds=settings.groq_timeout_seconds,
            max_output_tokens=settings.groq_max_output_tokens,
        )

    async def complete(self, prompt: str, user_id: str) -> GroqCompletion:
        started = perf_counter()
        try:
            response = await self._client.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Responda em portugues brasileiro de forma objetiva. "
                                "Nao invente dados financeiros do usuario."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "max_completion_tokens": self._max_output_tokens,
                    "temperature": 0.2,
                    "user": user_id,
                },
            )
        except httpx.TimeoutException as exc:
            raise GroqUnavailableError("A Groq demorou para responder.") from exc
        except httpx.HTTPError as exc:
            raise GroqUnavailableError("Nao foi possivel acessar a Groq.") from exc

        elapsed_ms = round((perf_counter() - started) * 1000)
        logger.info(
            "groq_request_completed user_id=%s model=%s status_code=%s duration_ms=%s prompt_chars=%s",
            user_id,
            self._model,
            response.status_code,
            elapsed_ms,
            len(prompt),
        )
        if response.status_code == 429:
            raise GroqRateLimitError("O limite temporario da IA foi atingido.")
        if response.status_code >= 500:
            raise GroqUnavailableError("A Groq esta temporariamente indisponivel.")
        if response.status_code >= 400:
            raise GroqServiceError("A Groq recusou a solicitacao.")

        payload = response.json()
        text = _response_text(payload)
        usage = payload.get("usage") if isinstance(payload, dict) else None
        usage = usage if isinstance(usage, dict) else {}
        return GroqCompletion(
            text=text,
            model=str(payload.get("model") or self._model),
            prompt_tokens=_optional_int(usage.get("prompt_tokens")),
            completion_tokens=_optional_int(usage.get("completion_tokens")),
            total_tokens=_optional_int(usage.get("total_tokens")),
        )

    async def close(self) -> None:
        await self._client.aclose()


def _response_text(payload: Any) -> str:
    try:
        text = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise GroqServiceError("A resposta da Groq nao continha texto.") from exc
    if not isinstance(text, str) or not text.strip():
        raise GroqServiceError("A resposta da Groq estava vazia.")
    return text.strip()


def _optional_int(value: object) -> int | None:
    return int(value) if isinstance(value, int) else None
