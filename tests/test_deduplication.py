from dataclasses import replace
from datetime import date
from decimal import Decimal

from finbot.models.transaction import TransactionDraft, TransactionStatus, TransactionType
from finbot.services.deduplication import build_transaction_dedupe_key


def make_draft(description: str = "Mercado") -> TransactionDraft:
    return TransactionDraft(
        type=TransactionType.EXPENSE,
        amount=Decimal("45"),
        transaction_date=date(2026, 7, 9),
        description=description,
        category="alimentacao",
        status=TransactionStatus.PAID,
    )


def test_dedupe_key_is_stable_for_text_spacing_and_case() -> None:
    assert build_transaction_dedupe_key(make_draft("Mercado")) == build_transaction_dedupe_key(
        make_draft("  mercado  ")
    )


def test_dedupe_key_changes_when_amount_changes() -> None:
    first = make_draft()
    second = replace(first, amount=Decimal("46"))

    assert build_transaction_dedupe_key(first) != build_transaction_dedupe_key(second)
