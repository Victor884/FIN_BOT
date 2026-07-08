from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum


class TransactionType(StrEnum):
    EXPENSE = "expense"
    INCOME = "income"
    TRANSFER = "transfer"
    ADJUSTMENT = "adjustment"


class TransactionStatus(StrEnum):
    PAID = "paid"
    PENDING = "pending"
    RECEIVED = "received"


@dataclass(frozen=True)
class TransactionDraft:
    type: TransactionType
    amount: Decimal
    transaction_date: date
    description: str
    category: str | None = None
    payment_method: str | None = None
    account_from: str | None = None
    account_to: str | None = None
    is_recurring: bool = False
    status: TransactionStatus = TransactionStatus.PAID
    confidence: float = 1.0

