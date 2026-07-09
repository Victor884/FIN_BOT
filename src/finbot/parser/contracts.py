from dataclasses import dataclass
from typing import Protocol

from finbot.models.transaction import TransactionDraft


@dataclass(frozen=True)
class ParseResult:
    draft: TransactionDraft | None
    missing_fields: tuple[str, ...] = ()
    needs_confirmation: bool = False
    raw_text: str = ""


class FinancialParser(Protocol):
    def parse(self, text: str) -> ParseResult:
        pass
