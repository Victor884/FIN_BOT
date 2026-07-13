import json
from datetime import UTC, date, datetime
from hashlib import sha256

from decimal import Decimal

from sqlalchemy import Select, func, select, update
from sqlalchemy.orm import Session

from finbot.db.models import (
    AccountRecord,
    CardRecord,
    CategoryRecord,
    RecurringTransactionRecord,
    TelegramConversationRecord,
    TransactionRecord,
    UserRecord,
)
from finbot.models.account import AccountDraft
from finbot.models.card import CardDraft
from finbot.models.transaction import TransactionDraft


class AccountRepository:
    def __init__(self, session: Session, user_id: str | None = None) -> None:
        self._session = session
        self.user_id = user_id

    def add(self, draft: AccountDraft) -> AccountRecord:
        record = AccountRecord.from_draft(draft)
        record.user_id = self.user_id
        self._session.add(record)
        self._session.flush()
        return record

    def get(self, account_id: str) -> AccountRecord | None:
        record = self._session.get(AccountRecord, account_id)
        if record is not None and self.user_id is not None and record.user_id != self.user_id:
            return None
        return record

    def get_by_name(self, name: str) -> AccountRecord | None:
        statement: Select[tuple[AccountRecord]] = select(AccountRecord).where(
            func.lower(AccountRecord.name) == name.strip().lower()
        )
        if self.user_id is not None:
            statement = statement.where(AccountRecord.user_id == self.user_id)
        return self._session.scalars(statement).first()

    def list(self, active_only: bool = True) -> list[AccountRecord]:
        statement: Select[tuple[AccountRecord]] = select(AccountRecord).order_by(
            AccountRecord.name.asc()
        )
        if active_only:
            statement = statement.where(AccountRecord.is_active.is_(True))
        if self.user_id is not None:
            statement = statement.where(AccountRecord.user_id == self.user_id)
        return list(self._session.scalars(statement))

    def adjust_balance(self, account_id: str, amount_delta: Decimal) -> AccountRecord | None:
        record = self.get(account_id)
        if record is None:
            return None
        record.current_balance += amount_delta
        self._session.flush()
        return record


class CardRepository:
    def __init__(self, session: Session, user_id: str | None = None) -> None:
        self._session = session
        self.user_id = user_id

    def add(self, draft: CardDraft) -> CardRecord:
        record = CardRecord.from_draft(draft)
        record.user_id = self.user_id
        self._session.add(record)
        self._session.flush()
        return record

    def get(self, card_id: str) -> CardRecord | None:
        record = self._session.get(CardRecord, card_id)
        if record is not None and self.user_id is not None and record.user_id != self.user_id:
            return None
        return record

    def get_by_name(self, name: str) -> CardRecord | None:
        statement: Select[tuple[CardRecord]] = select(CardRecord).where(
            func.lower(CardRecord.name) == name.strip().lower()
        )
        if self.user_id is not None:
            statement = statement.where(CardRecord.user_id == self.user_id)
        return self._session.scalars(statement).first()

    def list(self, active_only: bool = True) -> list[CardRecord]:
        statement: Select[tuple[CardRecord]] = select(CardRecord).order_by(CardRecord.name.asc())
        if active_only:
            statement = statement.where(CardRecord.is_active.is_(True))
        if self.user_id is not None:
            statement = statement.where(CardRecord.user_id == self.user_id)
        return list(self._session.scalars(statement))

    def adjust_invoice(self, card_id: str, amount_delta: Decimal) -> CardRecord | None:
        record = self.get(card_id)
        if record is None:
            return None
        record.current_invoice += amount_delta
        if record.current_invoice < 0:
            record.current_invoice = Decimal("0")
        self._session.flush()
        return record


class TransactionRepository:
    def __init__(self, session: Session, user_id: str | None = None) -> None:
        self._session = session
        self.user_id = user_id

    def add(self, draft: TransactionDraft, dedupe_key: str) -> TransactionRecord:
        scoped_key = self.scoped_dedupe_key(dedupe_key)
        record = TransactionRecord.from_draft(draft, scoped_key, user_id=self.user_id)
        self._session.add(record)
        self._session.flush()
        return record

    def scoped_dedupe_key(self, dedupe_key: str) -> str:
        if self.user_id is not None:
            return sha256(f"{self.user_id}:{dedupe_key}".encode()).hexdigest()
        return dedupe_key

    def update_from_draft(
        self, record: TransactionRecord, draft: TransactionDraft, dedupe_key: str
    ) -> TransactionRecord:
        record.type = draft.type.value
        record.amount = draft.amount
        record.transaction_date = draft.transaction_date
        record.description = draft.description
        record.category = draft.category
        record.payment_method = draft.payment_method
        record.account_from = draft.account_from
        record.account_to = draft.account_to
        record.card_name = draft.card_name
        record.is_recurring = draft.is_recurring
        record.installment_total = draft.installment_total
        record.status = draft.status.value
        record.confidence = draft.confidence
        record.dedupe_key = self.scoped_dedupe_key(dedupe_key)
        self._session.flush()
        return record

    def add_installment(
        self,
        draft: TransactionDraft,
        dedupe_key: str,
        *,
        group_id: str,
        number: int,
        total: int,
    ) -> TransactionRecord:
        record = self.add(draft, dedupe_key)
        record.installment_group_id = group_id
        record.installment_number = number
        record.installment_total = total
        self._session.flush()
        return record

    def get(self, transaction_id: str) -> TransactionRecord | None:
        record = self._session.get(TransactionRecord, transaction_id)
        if record is not None and self.user_id is not None and record.user_id != self.user_id:
            return None
        return record

    def get_by_dedupe_key(self, dedupe_key: str) -> TransactionRecord | None:
        statement: Select[tuple[TransactionRecord]] = select(TransactionRecord).where(
            TransactionRecord.dedupe_key
            == (
                sha256(f"{self.user_id}:{dedupe_key}".encode()).hexdigest()
                if self.user_id is not None
                else dedupe_key
            )
        )
        return self._session.scalars(statement).first()

    def list(self, limit: int = 100) -> list[TransactionRecord]:
        statement: Select[tuple[TransactionRecord]] = select(TransactionRecord)
        if self.user_id is not None:
            statement = statement.where(TransactionRecord.user_id == self.user_id)
        statement = statement.order_by(
            TransactionRecord.transaction_date.desc(), TransactionRecord.created_at.desc()
        ).limit(limit)
        return list(self._session.scalars(statement))

    def list_between(self, start_date: date, end_date: date) -> list[TransactionRecord]:
        statement: Select[tuple[TransactionRecord]] = (
            select(TransactionRecord)
            .where(TransactionRecord.transaction_date >= start_date)
            .where(TransactionRecord.transaction_date <= end_date)
            .order_by(TransactionRecord.transaction_date.asc(), TransactionRecord.created_at.asc())
        )
        if self.user_id is not None:
            statement = statement.where(TransactionRecord.user_id == self.user_id)
        return list(self._session.scalars(statement))

    def list_pending(self) -> list[TransactionRecord]:
        statement: Select[tuple[TransactionRecord]] = (
            select(TransactionRecord)
            .where(TransactionRecord.status == "pending")
            .order_by(TransactionRecord.transaction_date.asc(), TransactionRecord.created_at.asc())
        )
        if self.user_id is not None:
            statement = statement.where(TransactionRecord.user_id == self.user_id)
        return list(self._session.scalars(statement))

    def list_by_account(self, account_name: str, limit: int = 100) -> list[TransactionRecord]:
        statement: Select[tuple[TransactionRecord]] = select(TransactionRecord).where(
            (TransactionRecord.account_from == account_name)
            | (TransactionRecord.account_to == account_name)
        )
        if self.user_id is not None:
            statement = statement.where(TransactionRecord.user_id == self.user_id)
        statement = statement.order_by(
            TransactionRecord.transaction_date.desc(), TransactionRecord.created_at.desc()
        ).limit(limit)
        return list(self._session.scalars(statement))

    def list_unapplied_due(self, today: date) -> list[TransactionRecord]:
        statement = select(TransactionRecord).where(
            TransactionRecord.balance_applied.is_(False),
            TransactionRecord.transaction_date <= today,
        )
        if self.user_id is not None:
            statement = statement.where(TransactionRecord.user_id == self.user_id)
        return list(self._session.scalars(statement.order_by(TransactionRecord.transaction_date.asc())))

    def delete(self, record: TransactionRecord) -> None:
        self._session.delete(record)
        self._session.flush()


class CategoryRepository:
    def __init__(self, session: Session, user_id: str | None = None) -> None:
        self._session = session
        self.user_id = user_id

    def list(self) -> list[CategoryRecord]:
        if self.user_id is None:
            return []
        statement = select(CategoryRecord).where(CategoryRecord.user_id == self.user_id)
        return list(self._session.scalars(statement.order_by(CategoryRecord.name.asc())))

    def add(self, name: str) -> CategoryRecord:
        if self.user_id is None:
            raise ValueError("A user id is required for categories")
        normalized = name.strip().lower().replace(" ", "_")
        existing = self.get(normalized)
        if existing is not None:
            return existing
        record = CategoryRecord(user_id=self.user_id, name=normalized)
        self._session.add(record)
        self._session.flush()
        return record

    def get(self, name: str) -> CategoryRecord | None:
        if self.user_id is None:
            return None
        statement = select(CategoryRecord).where(
            CategoryRecord.user_id == self.user_id,
            func.lower(CategoryRecord.name) == name.strip().lower().replace(" ", "_"),
        )
        return self._session.scalars(statement).first()

    def delete_by_name(self, name: str) -> bool:
        record = self.get(name)
        if record is None:
            return False
        self._session.delete(record)
        self._session.flush()
        return True


class ConversationRepository:
    def __init__(self, session: Session, user_id: str | None = None) -> None:
        self._session = session
        self.user_id = user_id

    def get(self) -> TelegramConversationRecord | None:
        if self.user_id is None:
            return None
        record = self._session.get(TelegramConversationRecord, self.user_id)
        expires_at = record.expires_at.replace(tzinfo=UTC) if record and record.expires_at.tzinfo is None else (record.expires_at if record else None)
        if record is not None and expires_at is not None and expires_at <= datetime.now(UTC):
            self._session.delete(record)
            self._session.flush()
            return None
        return record

    def set(self, action: str, payload: dict[str, object], expires_at: datetime) -> None:
        if self.user_id is None:
            raise ValueError("A user id is required for conversations")
        record = self._session.get(TelegramConversationRecord, self.user_id)
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        now = datetime.now(UTC)
        if record is None:
            record = TelegramConversationRecord(
                user_id=self.user_id,
                action=action,
                payload_json=encoded,
                expires_at=expires_at,
            )
            self._session.add(record)
        else:
            record.action = action
            record.payload_json = encoded
            record.expires_at = expires_at
            record.updated_at = now
        self._session.flush()

    def payload(self, record: TelegramConversationRecord) -> dict[str, object]:
        return json.loads(record.payload_json)

    def clear(self) -> None:
        if self.user_id is None:
            return
        record = self._session.get(TelegramConversationRecord, self.user_id)
        if record is not None:
            self._session.delete(record)
            self._session.flush()


class RecurringTransactionRepository:
    def __init__(self, session: Session, user_id: str | None = None) -> None:
        self._session = session
        self.user_id = user_id

    def add(self, record: RecurringTransactionRecord) -> RecurringTransactionRecord:
        self._session.add(record)
        self._session.flush()
        return record

    def list_due(self, today: date) -> list[RecurringTransactionRecord]:
        statement = select(RecurringTransactionRecord).where(
            RecurringTransactionRecord.is_active.is_(True),
            RecurringTransactionRecord.next_due_date <= today,
        )
        if self.user_id is not None:
            statement = statement.where(RecurringTransactionRecord.user_id == self.user_id)
        return list(self._session.scalars(statement.order_by(RecurringTransactionRecord.next_due_date.asc())))


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: str) -> UserRecord | None:
        return self._session.get(UserRecord, user_id)

    def get_by_email(self, email: str) -> UserRecord | None:
        statement = select(UserRecord).where(func.lower(UserRecord.email) == email.strip().lower())
        return self._session.scalars(statement).first()

    def get_or_create_telegram(
        self,
        telegram_user_id: int | str,
        chat_id: int | str,
        name: str | None,
        username: str | None,
    ) -> UserRecord:
        telegram_id = str(telegram_user_id)
        statement = select(UserRecord).where(UserRecord.telegram_user_id == telegram_id)
        user = self._session.scalars(statement).first()
        now = datetime.now(UTC)
        if user is None:
            is_first_telegram_user = not bool(
                self._session.scalar(
                    select(func.count(UserRecord.id)).where(UserRecord.telegram_user_id.is_not(None))
                )
            )
            user = UserRecord(
                telegram_user_id=telegram_id,
                chat_id=str(chat_id),
                name=name,
                username=username,
                last_activity_at=now,
            )
            self._session.add(user)
            self._session.flush()
            if is_first_telegram_user:
                self._claim_legacy_records(user.id)
        else:
            user.chat_id = str(chat_id)
            user.name = name or user.name
            user.username = username or user.username
            user.last_activity_at = now
        self._session.flush()
        return user

    def _claim_legacy_records(self, user_id: str) -> None:
        self._session.execute(
            update(AccountRecord).where(AccountRecord.user_id.is_(None)).values(user_id=user_id)
        )
        self._session.execute(
            update(CardRecord).where(CardRecord.user_id.is_(None)).values(user_id=user_id)
        )
        legacy_transactions = list(
            self._session.scalars(
                select(TransactionRecord).where(TransactionRecord.user_id.is_(None))
            )
        )
        for record in legacy_transactions:
            record.user_id = user_id
            record.dedupe_key = sha256(f"{user_id}:{record.dedupe_key}".encode()).hexdigest()

    def add_web_user(self, name: str, email: str, password_hash: str, role: str = "USER") -> UserRecord:
        user = UserRecord(
            name=name.strip(),
            email=email.strip().lower(),
            password_hash=password_hash,
            role=role,
        )
        self._session.add(user)
        self._session.flush()
        return user
