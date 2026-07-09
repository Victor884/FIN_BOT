from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class AccountType(StrEnum):
    BANK = "banco"
    WALLET = "carteira"
    CARD = "cartao"
    SAVINGS = "poupanca"
    INVESTMENT = "investimento"
    OTHER = "outro"


@dataclass(frozen=True)
class AccountDraft:
    name: str
    type: AccountType
    initial_balance: Decimal = Decimal("0")
    current_balance: Decimal | None = None
    is_active: bool = True


@dataclass(frozen=True)
class Account:
    id: str
    name: str
    type: AccountType
    initial_balance: Decimal
    current_balance: Decimal
    is_active: bool
    created_at: datetime
