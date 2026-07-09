import hashlib
import re
import unicodedata

from finbot.models.transaction import TransactionDraft


def build_transaction_dedupe_key(draft: TransactionDraft) -> str:
    parts = (
        draft.type.value,
        f"{draft.amount:.2f}",
        draft.transaction_date.isoformat(),
        _normalize(draft.description),
        _normalize(draft.category),
        _normalize(draft.payment_method),
        _normalize(draft.account_from),
        _normalize(draft.account_to),
    )
    raw_key = "|".join(parts)
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _normalize(value: str | None) -> str:
    if value is None:
        return ""

    lowered = value.strip().lower()
    normalized = unicodedata.normalize("NFKD", lowered)
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", ascii_text)

