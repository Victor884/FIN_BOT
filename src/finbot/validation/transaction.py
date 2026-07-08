from finbot.models.transaction import TransactionDraft


def validate_transaction_draft(draft: TransactionDraft) -> list[str]:
    errors: list[str] = []

    if draft.amount <= 0:
        errors.append("amount_must_be_positive")

    if not draft.description.strip():
        errors.append("description_required")

    return errors

