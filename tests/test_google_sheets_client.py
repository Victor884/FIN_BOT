from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from finbot.core.errors import ConfigurationError
from finbot.core.settings import Settings
from finbot.db.models import TransactionRecord
from finbot.sheets.client import DEFAULT_TRANSACTIONS_RANGE, GoogleSheetsClient
from finbot.sheets.rows import TRANSACTION_HEADERS, transaction_to_sheet_row


class FakeAppendRequest:
    def __init__(self, response: dict[str, object]) -> None:
        self._response = response

    def execute(self) -> dict[str, object]:
        return self._response


class FakeValuesResource:
    def __init__(self) -> None:
        self.append_kwargs: dict[str, object] | None = None

    def append(self, **kwargs: object) -> FakeAppendRequest:
        self.append_kwargs = kwargs
        return FakeAppendRequest({"updates": {"updatedRows": 1}})


class FakeSpreadsheetsResource:
    def __init__(self, values_resource: FakeValuesResource) -> None:
        self._values_resource = values_resource

    def values(self) -> FakeValuesResource:
        return self._values_resource


class FakeSheetsService:
    def __init__(self) -> None:
        self.values_resource = FakeValuesResource()

    def spreadsheets(self) -> FakeSpreadsheetsResource:
        return FakeSpreadsheetsResource(self.values_resource)


def make_transaction() -> TransactionRecord:
    return TransactionRecord(
        id="transaction-id",
        type="expense",
        amount=Decimal("45.90"),
        transaction_date=date(2026, 7, 9),
        description="mercado",
        category="alimentacao",
        payment_method="pix",
        account_from="conta corrente",
        account_to=None,
        is_recurring=False,
        status="paid",
        confidence=Decimal("0.850"),
        dedupe_key="dedupe-key",
        created_at=datetime(2026, 7, 9, 12, 0, tzinfo=UTC),
    )


def test_transaction_headers_match_row_length() -> None:
    row = transaction_to_sheet_row(make_transaction())

    assert len(TRANSACTION_HEADERS) == len(row)


def test_transaction_to_sheet_row_formats_values() -> None:
    row = transaction_to_sheet_row(make_transaction())

    assert row == [
        "transaction-id",
        "2026-07-09",
        "expense",
        "45.90",
        "alimentacao",
        "pix",
        "conta corrente",
        "",
        "mercado",
        "nao",
        "paid",
        "0.85",
        "dedupe-key",
        "2026-07-09T12:00:00+00:00",
    ]


def test_append_transaction_calls_google_values_append() -> None:
    fake_service = FakeSheetsService()
    client = GoogleSheetsClient(service=fake_service, spreadsheet_id="sheet-id")

    response = client.append_transaction(make_transaction())

    assert response == {"updates": {"updatedRows": 1}}
    assert fake_service.values_resource.append_kwargs == {
        "spreadsheetId": "sheet-id",
        "range": DEFAULT_TRANSACTIONS_RANGE,
        "valueInputOption": "USER_ENTERED",
        "insertDataOption": "INSERT_ROWS",
        "body": {"values": [transaction_to_sheet_row(make_transaction())]},
    }


def test_from_settings_requires_spreadsheet_id() -> None:
    settings = Settings(google_sheets_spreadsheet_id=None, google_service_account_file="sa.json")

    with pytest.raises(ConfigurationError):
        GoogleSheetsClient.from_settings(settings)


def test_from_settings_requires_service_account_file() -> None:
    settings = Settings(google_sheets_spreadsheet_id="sheet-id", google_service_account_file=None)

    with pytest.raises(ConfigurationError):
        GoogleSheetsClient.from_settings(settings)
