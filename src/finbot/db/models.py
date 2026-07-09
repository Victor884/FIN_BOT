from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from finbot.db.base import Base
from finbot.models.account import AccountDraft, AccountType
from finbot.models.card import CardDraft, CardType
from finbot.models.transaction import TransactionDraft, TransactionStatus, TransactionType


class AccountRecord(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    initial_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    current_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    @classmethod
    def from_draft(cls, draft: AccountDraft) -> "AccountRecord":
        current_balance = draft.current_balance
        if current_balance is None:
            current_balance = draft.initial_balance
        return cls(
            name=draft.name,
            type=draft.type.value,
            initial_balance=draft.initial_balance,
            current_balance=current_balance,
            is_active=draft.is_active,
        )

    @property
    def account_type(self) -> AccountType:
        return AccountType(self.type)


class CardRecord(Base):
    __tablename__ = "cards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    linked_account_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    limit: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    closing_day: Mapped[int | None] = mapped_column(nullable=True)
    due_day: Mapped[int | None] = mapped_column(nullable=True)
    current_invoice: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    @classmethod
    def from_draft(cls, draft: CardDraft) -> "CardRecord":
        return cls(
            name=draft.name,
            type=draft.type.value,
            linked_account_id=draft.linked_account_id,
            limit=draft.limit,
            closing_day=draft.closing_day,
            due_day=draft.due_day,
            current_invoice=draft.current_invoice,
            is_active=draft.is_active,
        )

    @property
    def card_type(self) -> CardType:
        return CardType(self.type)


class TransactionRecord(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    payment_method: Mapped[str | None] = mapped_column(String(80), nullable=True)
    account_from: Mapped[str | None] = mapped_column(String(120), nullable=True)
    account_to: Mapped[str | None] = mapped_column(String(120), nullable=True)
    card_name: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    @classmethod
    def from_draft(cls, draft: TransactionDraft, dedupe_key: str) -> "TransactionRecord":
        return cls(
            type=draft.type.value,
            amount=draft.amount,
            transaction_date=draft.transaction_date,
            description=draft.description,
            category=draft.category,
            payment_method=draft.payment_method,
            account_from=draft.account_from,
            account_to=draft.account_to,
            card_name=draft.card_name,
            is_recurring=draft.is_recurring,
            status=draft.status.value,
            confidence=Decimal(str(draft.confidence)),
            dedupe_key=dedupe_key,
        )

    def to_draft(self) -> TransactionDraft:
        return TransactionDraft(
            type=TransactionType(self.type),
            amount=self.amount,
            transaction_date=self.transaction_date,
            description=self.description,
            category=self.category,
            payment_method=self.payment_method,
            account_from=self.account_from,
            account_to=self.account_to,
            card_name=self.card_name,
            is_recurring=self.is_recurring,
            status=TransactionStatus(self.status),
            confidence=float(self.confidence),
        )
