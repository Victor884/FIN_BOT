from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from finbot.db.base import Base
from finbot.models.account import AccountDraft, AccountType
from finbot.models.card import CardDraft, CardType
from finbot.models.transaction import TransactionDraft, TransactionStatus, TransactionType


class AccountRecord(Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_accounts_user_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
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
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_cards_user_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
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
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
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
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="telegram", index=True)
    sheets_synced: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    needs_confirmation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    @classmethod
    def from_draft(
        cls,
        draft: TransactionDraft,
        dedupe_key: str,
        user_id: str | None = None,
        source: str = "telegram",
    ) -> "TransactionRecord":
        return cls(
            user_id=user_id,
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
            source=source,
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


class UserRecord(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    telegram_user_id: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True, index=True)
    chat_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    username: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(254), unique=True, nullable=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="USER", index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), index=True
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), index=True
    )


class TelegramUpdateRecord(Base):
    __tablename__ = "telegram_updates"

    update_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    parser_source: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    ai_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    duplicate_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    parser_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    validation_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    database_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    telegram_response_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), index=True
    )


class RequestMetricRecord(Base):
    __tablename__ = "request_metrics"
    __table_args__ = (
        Index("ix_request_metrics_endpoint_created", "endpoint", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    endpoint: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    origin: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), index=True
    )


class ApplicationErrorRecord(Base):
    __tablename__ = "application_errors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    request_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    endpoint: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    integration: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), index=True
    )


class RefreshTokenRecord(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class WebLinkCodeRecord(Base):
    __tablename__ = "web_link_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
