from collections.abc import Sequence
from typing import Protocol

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from finbot.core.errors import ConfigurationError
from finbot.core.settings import Settings
from finbot.db.models import TransactionRecord
from finbot.sheets.rows import transaction_to_sheet_row


SHEETS_SCOPES = ("https://www.googleapis.com/auth/spreadsheets",)
DEFAULT_TRANSACTIONS_RANGE = "Lancamentos!A:N"


class SheetsValuesResource(Protocol):
    def append(self, **kwargs: object) -> object:
        pass


class SheetsSpreadsheetsResource(Protocol):
    def values(self) -> SheetsValuesResource:
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
        request = (
            self._service.spreadsheets()
            .values()
            .append(
                spreadsheetId=self._spreadsheet_id,
                range=self._transactions_range,
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": [row]},
            )
        )
        response = request.execute()
        return dict(response)

    def append_transactions(self, transactions: Sequence[TransactionRecord]) -> list[dict[str, object]]:
        return [self.append_transaction(transaction) for transaction in transactions]
