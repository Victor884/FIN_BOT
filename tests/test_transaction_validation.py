from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

from finbot.models.transaction import TransactionDraft, TransactionStatus, TransactionType
from finbot.validation.transaction import validate_transaction, validate_transaction_draft


def make_draft(**overrides: object) -> TransactionDraft:
    draft = TransactionDraft(
        type=TransactionType.EXPENSE,
        amount=Decimal("45"),
        transaction_date=date.today(),
        description="mercado",
        category="alimentacao",
        status=TransactionStatus.PAID,
        confidence=0.85,
    )
    return replace(draft, **overrides)


def test_valid_expense_has_no_errors() -> None:
    result = validate_transaction(make_draft())

    assert result.is_valid
    assert result.errors == ()
    assert result.warnings == ()


def test_legacy_validation_returns_error_list() -> None:
    errors = validate_transaction_draft(make_draft(amount=Decimal("0")))

    assert errors == ["amount_must_be_positive"]


def test_transfer_requires_origin_and_destination_accounts() -> None:
    result = validate_transaction(
        make_draft(type=TransactionType.TRANSFER, category=None, account_from=None, account_to=None)
    )

    assert not result.is_valid
    assert "account_from_required_for_transfer" in result.errors
    assert "account_to_required_for_transfer" in result.errors


def test_transfer_accounts_must_be_different() -> None:
    result = validate_transaction(
        make_draft(
            type=TransactionType.TRANSFER,
            category=None,
            account_from="conta corrente",
            account_to="conta corrente",
        )
    )

    assert result.errors == ("transfer_accounts_must_be_different",)


def test_income_cannot_have_paid_status() -> None:
    result = validate_transaction(make_draft(type=TransactionType.INCOME, status=TransactionStatus.PAID))

    assert result.errors == ("status_incompatible_with_type",)


def test_missing_category_is_warning_for_expense() -> None:
    result = validate_transaction(make_draft(category=None))

    assert result.is_valid
    assert result.warnings == ("category_missing",)


def test_low_confidence_is_warning() -> None:
    result = validate_transaction(make_draft(confidence=0.4))

    assert result.is_valid
    assert result.warnings == ("low_parser_confidence",)


def test_invalid_confidence_is_error() -> None:
    result = validate_transaction(make_draft(confidence=1.5))

    assert result.errors == ("confidence_must_be_between_zero_and_one",)


def test_future_date_is_warning() -> None:
    result = validate_transaction(make_draft(transaction_date=date.today() + timedelta(days=1)))

    assert result.is_valid
    assert result.warnings == ("transaction_date_is_future",)
