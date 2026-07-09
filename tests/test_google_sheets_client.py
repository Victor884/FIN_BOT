from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from finbot.core.errors import ConfigurationError
from finbot.core.settings import Settings
from finbot.db.models import TransactionRecord
from finbot.services.queries import FinancialSummary
from finbot.sheets.client import DEFAULT_TRANSACTIONS_RANGE, GoogleSheetsClient
from finbot.sheets.rows import TRANSACTION_HEADERS, transaction_to_sheet_row


class FakeAppendRequest:
    def __init__(self, response: dict[str, object]) -> None:
        self._response = response

    def execute(self) -> dict[str, object]:
        return self._response


class FakeUpdateRequest(FakeAppendRequest):
    pass


class FakeValuesResource:
    def __init__(self) -> None:
        self.append_kwargs: dict[str, object] | None = None
        self.update_calls: list[dict[str, object]] = []

    def append(self, **kwargs: object) -> FakeAppendRequest:
        self.append_kwargs = kwargs
        return FakeAppendRequest({"updates": {"updatedRows": 1}})

    def update(self, **kwargs: object) -> FakeUpdateRequest:
        self.update_calls.append(kwargs)
        return FakeUpdateRequest({"updatedRows": 1})


class FakeSpreadsheetsResource:
    def __init__(self, values_resource: FakeValuesResource) -> None:
        self._values_resource = values_resource
        self.batch_update_kwargs: dict[str, object] | None = None

    def values(self) -> FakeValuesResource:
        return self._values_resource

    def batchUpdate(self, **kwargs: object) -> FakeUpdateRequest:
        self.batch_update_kwargs = kwargs
        return FakeUpdateRequest({"replies": []})


class FakeSheetsService:
    def __init__(self) -> None:
        self.values_resource = FakeValuesResource()
        self.spreadsheets_resource = FakeSpreadsheetsResource(self.values_resource)

    def spreadsheets(self) -> FakeSpreadsheetsResource:
        return self.spreadsheets_resource


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
        card_name="",
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
        "mercado",
        "alimentacao",
        "45.90",
        "conta corrente",
        "",
        "conta corrente",
        "",
        "pix",
        "paid",
        "2026-07",
        2026,
        "",
        "2026-07-09T12:00:00+00:00",
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


def test_setup_workbook_creates_sheets_and_headers() -> None:
    fake_service = FakeSheetsService()
    client = GoogleSheetsClient(service=fake_service, spreadsheet_id="sheet-id")

    responses = client.setup_workbook()

    assert responses[0] == {"replies": []}
    assert fake_service.spreadsheets_resource.batch_update_kwargs is not None
    batch_body = fake_service.spreadsheets_resource.batch_update_kwargs["body"]
    assert isinstance(batch_body, dict)
    assert len(batch_body["requests"]) == 12
    assert len(fake_service.values_resource.update_calls) > 12
    assert fake_service.values_resource.update_calls[0] == {
        "spreadsheetId": "sheet-id",
        "range": "Lancamentos!A1",
        "valueInputOption": "USER_ENTERED",
        "body": {"values": [list(TRANSACTION_HEADERS)]},
    }
    assert any(call["range"] == "Dashboard!A2" for call in fake_service.values_resource.update_calls)


def test_update_financial_dashboard_updates_expected_ranges() -> None:
    fake_service = FakeSheetsService()
    client = GoogleSheetsClient(service=fake_service, spreadsheet_id="sheet-id")
    transaction = make_transaction()
    summary = FinancialSummary(
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 31),
        total_income=Decimal("2500"),
        total_expenses=Decimal("45.90"),
        balance=Decimal("2454.10"),
        pending_total=Decimal("0"),
        expenses_by_category={"alimentacao": Decimal("45.90")},
        largest_expenses=(transaction,),
    )

    responses = client.update_financial_dashboard(summary, pending_transactions=[transaction])

    assert len(responses) == 5
    assert [call["range"] for call in fake_service.values_resource.update_calls] == [
        "Dashboard!A2",
        "Dashboard!A8",
        "Resumo_Mensal!A2",
        "Resumo_Categoria!A2",
        "Pendentes!A2",
    ]


def test_from_settings_requires_spreadsheet_id() -> None:
    settings = Settings(google_sheets_spreadsheet_id=None, google_service_account_file="sa.json")

    with pytest.raises(ConfigurationError):
        GoogleSheetsClient.from_settings(settings)


def test_from_settings_requires_service_account_file() -> None:
    settings = Settings(google_sheets_spreadsheet_id="sheet-id", google_service_account_file=None)

    with pytest.raises(ConfigurationError):
        GoogleSheetsClient.from_settings(settings)
