from datetime import date
from decimal import Decimal

from finbot.models.transaction import TransactionDraft, TransactionStatus, TransactionType
from finbot.parser.composite import CompositeFinancialParser
from finbot.parser.contracts import ParseResult


class FakeParser:
    def __init__(self, result: ParseResult) -> None:
        self.result = result
        self.calls = 0

    def parse(self, text: str) -> ParseResult:
        self.calls += 1
        return self.result


def make_draft() -> TransactionDraft:
    return TransactionDraft(
        type=TransactionType.EXPENSE,
        amount=Decimal("45"),
        transaction_date=date(2026, 7, 9),
        description="mercado",
        status=TransactionStatus.PAID,
    )


def test_composite_parser_uses_primary_when_complete() -> None:
    primary = FakeParser(ParseResult(draft=make_draft()))
    fallback = FakeParser(ParseResult(draft=None))
    parser = CompositeFinancialParser(primary=primary, fallback=fallback)

    result = parser.parse("Gastei R$ 45 no mercado")

    assert result.draft == make_draft()
    assert primary.calls == 1
    assert fallback.calls == 0


def test_composite_parser_uses_fallback_when_primary_is_incomplete() -> None:
    primary = FakeParser(ParseResult(draft=None, missing_fields=("amount",)))
    fallback = FakeParser(ParseResult(draft=make_draft()))
    parser = CompositeFinancialParser(primary=primary, fallback=fallback)

    result = parser.parse("mercado")

    assert result.draft == make_draft()
    assert primary.calls == 1
    assert fallback.calls == 1
