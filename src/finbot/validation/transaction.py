from dataclasses import dataclass
from datetime import date

from finbot.models.transaction import TransactionDraft
from finbot.models.transaction import TransactionStatus
from finbot.models.transaction import TransactionType


MIN_CONFIDENCE = 0.7
VALID_STATUSES_BY_TYPE = {
    TransactionType.EXPENSE: {TransactionStatus.PAID, TransactionStatus.PENDING},
    TransactionType.INCOME: {TransactionStatus.RECEIVED, TransactionStatus.PENDING},
    TransactionType.TRANSFER: {TransactionStatus.PAID, TransactionStatus.PENDING},
    TransactionType.ADJUSTMENT: {TransactionStatus.PAID},
}


@dataclass(frozen=True)
class ValidationResult:
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def is_valid(self) -> bool:
        return not self.errors


def validate_transaction_draft(draft: TransactionDraft) -> list[str]:
    return list(validate_transaction(draft).errors)


def validate_transaction(draft: TransactionDraft) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if draft.amount <= 0:
        errors.append("amount_must_be_positive")

    if not draft.description.strip():
        errors.append("description_required")

    if draft.transaction_date > date.today():
        warnings.append("transaction_date_is_future")

    if not 0 <= draft.confidence <= 1:
        errors.append("confidence_must_be_between_zero_and_one")
    elif draft.confidence < MIN_CONFIDENCE:
        warnings.append("low_parser_confidence")

    expected_statuses = VALID_STATUSES_BY_TYPE[draft.type]
    if draft.status not in expected_statuses:
        errors.append("status_incompatible_with_type")

    if draft.type == TransactionType.TRANSFER:
        if not draft.account_from:
            errors.append("account_from_required_for_transfer")
        if not draft.account_to:
            errors.append("account_to_required_for_transfer")
        if draft.account_from and draft.account_to and draft.account_from == draft.account_to:
            errors.append("transfer_accounts_must_be_different")

    if draft.type in {TransactionType.EXPENSE, TransactionType.INCOME} and not draft.category:
        warnings.append("category_missing")

    return ValidationResult(errors=tuple(errors), warnings=tuple(warnings))
