from collections.abc import Sequence
from typing import Protocol

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from finbot.core.errors import ConfigurationError
from finbot.core.settings import Settings
from finbot.db.models import TransactionRecord
from finbot.sheets.dashboard import category_month_rows
from finbot.sheets.dashboard import dashboard_rows_from_summary
from finbot.sheets.dashboard import largest_expense_rows
from finbot.sheets.dashboard import monthly_summary_row
from finbot.sheets.dashboard import pending_rows
from finbot.sheets.layout import SheetDefinition
from finbot.sheets.layout import build_create_missing_sheets_request
from finbot.sheets.layout import default_sheet_definitions
from finbot.sheets.layout import default_formula_updates
from finbot.sheets.rows import transaction_to_sheet_row
from finbot.services.queries import FinancialSummary


SHEETS_SCOPES = ("https://www.googleapis.com/auth/spreadsheets",)
DEFAULT_TRANSACTIONS_RANGE = "Lancamentos!A:Q"


class SheetsValuesResource(Protocol):
    def append(self, **kwargs: object) -> object:
        pass

    def update(self, **kwargs: object) -> object:
        pass


class SheetsSpreadsheetsResource(Protocol):
    def values(self) -> SheetsValuesResource:
        pass

    def get(self, **kwargs: object) -> object:
        pass

    def batchUpdate(self, **kwargs: object) -> object:
        pass


class SheetsService(Protocol):
    def spreadsheets(self) -> SheetsSpreadsheetsResource:
        pass


class GoogleSheetsClient:
    def __init__(
        self,
        service: SheetsService,
        spreadsheet_id: str,
        transactions_range: str = DEFAULT_TRANSACTIONS_RANGE,
    ) -> None:
        self._service = service
        self._spreadsheet_id = spreadsheet_id
        self._transactions_range = transactions_range

    @classmethod
    def from_settings(cls, settings: Settings) -> "GoogleSheetsClient":
        if not settings.google_sheets_spreadsheet_id:
            raise ConfigurationError("GOOGLE_SHEETS_SPREADSHEET_ID is required")
        if not settings.google_service_account_file:
            raise ConfigurationError("GOOGLE_SERVICE_ACCOUNT_FILE is required")

        credentials = Credentials.from_service_account_file(
            settings.google_service_account_file,
            scopes=list(SHEETS_SCOPES),
        )
        service = build("sheets", "v4", credentials=credentials)
        return cls(service=service, spreadsheet_id=settings.google_sheets_spreadsheet_id)

    def append_transaction(self, transaction: TransactionRecord) -> dict[str, object]:
        row = transaction_to_sheet_row(transaction)
        return self.append_transaction_row(row)

    def append_transaction_row(self, row: Sequence[object]) -> dict[str, object]:
        request = (
            self._service.spreadsheets()
            .values()
            .append(
                spreadsheetId=self._spreadsheet_id,
                range=self._transactions_range,
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": [list(row)]},
            )
        )
        response = request.execute()
        return dict(response)

    def append_transactions(self, transactions: Sequence[TransactionRecord]) -> list[dict[str, object]]:
        return [self.append_transaction(transaction) for transaction in transactions]

    def setup_workbook(
        self,
        sheet_definitions: Sequence[SheetDefinition] | None = None,
    ) -> list[dict[str, object]]:
        definitions = tuple(sheet_definitions or default_sheet_definitions())
        existing_titles = self._existing_sheet_titles()
        missing_definitions = tuple(
            definition for definition in definitions if definition.title not in existing_titles
        )
        responses = []

        if missing_definitions:
            responses.append(self._batch_update(build_create_missing_sheets_request(missing_definitions)))

        for definition in definitions:
            responses.append(
                self.update_values(
                    range_name=f"{definition.title}!A1",
                    values=[list(definition.headers)],
                )
            )

        for range_name, values in default_formula_updates():
            responses.append(self.update_values(range_name=range_name, values=values))

        return responses

    def _existing_sheet_titles(self) -> set[str]:
        request = self._service.spreadsheets().get(
            spreadsheetId=self._spreadsheet_id,
            fields="sheets.properties.title",
        )
        response = request.execute()
        sheets = response.get("sheets", [])
        titles = {
            sheet.get("properties", {}).get("title")
            for sheet in sheets
            if sheet.get("properties", {}).get("title")
        }
        return {str(title) for title in titles}

    def update_values(self, range_name: str, values: Sequence[Sequence[object]]) -> dict[str, object]:
        request = (
            self._service.spreadsheets()
            .values()
            .update(
                spreadsheetId=self._spreadsheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                body={"values": [list(row) for row in values]},
            )
        )
        response = request.execute()
        return dict(response)

    def update_financial_dashboard(
        self,
        summary: FinancialSummary,
        pending_transactions: Sequence[TransactionRecord],
    ) -> list[dict[str, object]]:
        return [
            self.update_values("Dashboard!A2", dashboard_rows_from_summary(summary)),
            self.update_values("Dashboard!A8", largest_expense_rows(summary)),
            self.update_values("Resumo_Mensal!A2", [monthly_summary_row(summary)]),
            self.update_values("Resumo_Categoria!A2", category_month_rows(summary)),
            self.update_values("Pendentes!A2", pending_rows(list(pending_transactions))),
        ]

    def _batch_update(self, body: dict[str, object]) -> dict[str, object]:
        request = self._service.spreadsheets().batchUpdate(
            spreadsheetId=self._spreadsheet_id,
            body=body,
        )
        response = request.execute()
        return dict(response)
