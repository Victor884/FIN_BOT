from dataclasses import dataclass

from finbot.models.transaction import TransactionDraft


@dataclass(frozen=True)
class ParseResult:
    draft: TransactionDraft | None
    missing_fields: tuple[str, ...] = ()
    needs_confirmation: bool = False
    raw_text: str = ""

