import json
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from finbot.core.errors import ConfigurationError, FinbotError
from finbot.core.settings import Settings
from finbot.models.transaction import TransactionDraft, TransactionStatus, TransactionType
from finbot.parser.contracts import ParseResult


class AIParserError(FinbotError):
    """Raised when the AI parser response cannot be used."""


class OpenAIFinancialParser:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=20)

    @classmethod
    def from_settings(cls, settings: Settings) -> "OpenAIFinancialParser":
        if not settings.openai_api_key:
            raise ConfigurationError("OPENAI_API_KEY is required when AI_ENABLED=true")
        return cls(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
        )

    def parse(self, text: str) -> ParseResult:
        payload = {
            "model": self._model,
            "input": _build_prompt(text),
            "max_output_tokens": 500,
        }
        response = self._client.post(
            f"{self._base_url}/responses",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        content = _extract_response_text(response.json())
        data = _parse_json_payload(content)
        draft = _draft_from_payload(data)
        missing_fields = tuple(data.get("missing_fields", ()))
        return ParseResult(
            draft=draft,
            missing_fields=missing_fields,
            needs_confirmation=bool(data.get("needs_confirmation", False)),
            raw_text=text,
        )


def _build_prompt(text: str) -> str:
    today = date.today().isoformat()
    return (
        "Interprete a mensagem financeira em portugues e responda apenas JSON valido. "
        f"Data de hoje: {today}. "
        "Campos: type expense|income|transfer|adjustment, amount number, "
        "transaction_date YYYY-MM-DD, description string, category string|null, "
        "payment_method string|null, account_from string|null, account_to string|null, "
        "is_recurring boolean, status paid|pending|received, confidence number, "
        "needs_confirmation boolean, missing_fields array. "
        f"Mensagem: {text}"
    )


def _extract_response_text(response_payload: dict[str, Any]) -> str:
    if isinstance(response_payload.get("output_text"), str):
        return response_payload["output_text"]

    output = response_payload.get("output", [])
    for item in output:
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                return content["text"]

    raise AIParserError("OpenAI response did not include text output")


def _parse_json_payload(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise AIParserError("OpenAI response was not valid JSON") from exc

    if not isinstance(parsed, dict):
        raise AIParserError("OpenAI response JSON must be an object")
    return parsed


def _draft_from_payload(payload: dict[str, Any]) -> TransactionDraft | None:
    missing_fields = set(payload.get("missing_fields", ()))
    if missing_fields:
        return None

    try:
        amount = Decimal(str(payload["amount"]))
        transaction_date = date.fromisoformat(str(payload["transaction_date"]))
        transaction_type = TransactionType(str(payload["type"]))
        status = TransactionStatus(str(payload["status"]))
    except (KeyError, ValueError, InvalidOperation) as exc:
        raise AIParserError("OpenAI response has invalid transaction fields") from exc

    return TransactionDraft(
        type=transaction_type,
        amount=amount,
        transaction_date=transaction_date,
        description=str(payload.get("description") or "movimentacao"),
        category=payload.get("category"),
        payment_method=payload.get("payment_method"),
        account_from=payload.get("account_from"),
        account_to=payload.get("account_to"),
        is_recurring=bool(payload.get("is_recurring", False)),
        status=status,
        confidence=float(payload.get("confidence", 0.75)),
    )
