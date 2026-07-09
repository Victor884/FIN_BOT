from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class CardType(StrEnum):
    CREDIT = "credito"
    DEBIT = "debito"


@dataclass(frozen=True)
class CardDraft:
    name: str
    type: CardType
    linked_account_id: str | None = None
    limit: Decimal | None = None
    closing_day: int | None = None
    due_day: int | None = None
    current_invoice: Decimal = Decimal("0")
    is_active: bool = True


@dataclass(frozen=True)
class Card:
    id: str
    name: str
    type: CardType
    linked_account_id: str | None
    limit: Decimal | None
    closing_day: int | None
    due_day: int | None
    current_invoice: Decimal
    is_active: bool
    created_at: datetime
