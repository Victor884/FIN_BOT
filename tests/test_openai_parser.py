from datetime import date
from decimal import Decimal

import httpx
import pytest

from finbot.ai.openai_parser import AIParserError, OpenAIFinancialParser
from finbot.core.errors import ConfigurationError
from finbot.core.settings import Settings
from finbot.models.transaction import TransactionStatus, TransactionType


def make_client(response_payload: dict[str, object]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/responses"
        assert request.headers["Authorization"] == "Bearer test-key"
        return httpx.Response(200, json=response_payload)

    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://example.test")


def test_openai_parser_parses_output_text_json() -> None:
    client = make_client(
        {
            "output_text": (
                '{"type":"expense","amount":45,"transaction_date":"2026-07-09",'
                '"description":"mercado","category":"alimentacao","payment_method":"pix",'
                '"account_from":null,"account_to":null,"is_recurring":false,'
                '"status":"paid","confidence":0.82,"needs_confirmation":false,'
                '"missing_fields":[]}'
            )
        }
    )
    parser = OpenAIFinancialParser(
        api_key="test-key",
        model="gpt-5.4-nano",
        base_url="https://example.test",
        client=client,
    )

    result = parser.parse("mercado 45 pix")

    assert result.draft is not None
    assert result.draft.type == TransactionType.EXPENSE
    assert result.draft.amount == Decimal("45")
    assert result.draft.transaction_date == date(2026, 7, 9)
    assert result.draft.status == TransactionStatus.PAID
    assert result.draft.category == "alimentacao"


def test_openai_parser_returns_missing_fields_without_draft() -> None:
    client = make_client(
        {
            "output_text": (
                '{"missing_fields":["amount"],"needs_confirmation":true}'
            )
        }
    )
    parser = OpenAIFinancialParser(
        api_key="test-key",
        model="gpt-5.4-nano",
        base_url="https://example.test",
        client=client,
    )

    result = parser.parse("mercado")

    assert result.draft is None
    assert result.missing_fields == ("amount",)
    assert result.needs_confirmation


def test_openai_parser_rejects_invalid_json() -> None:
    client = make_client({"output_text": "not json"})
    parser = OpenAIFinancialParser(
        api_key="test-key",
        model="gpt-5.4-nano",
        base_url="https://example.test",
        client=client,
    )

    with pytest.raises(AIParserError):
        parser.parse("mercado")


def test_openai_parser_from_settings_requires_api_key() -> None:
    settings = Settings(ai_enabled=True, openai_api_key=None)

    with pytest.raises(ConfigurationError):
        OpenAIFinancialParser.from_settings(settings)
