from datetime import UTC, date, datetime
from hashlib import sha256

from decimal import Decimal

from sqlalchemy import Select, func, select, update
from sqlalchemy.orm import Session

from finbot.db.models import AccountRecord, CardRecord, TransactionRecord, UserRecord
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
        scoped_key = dedupe_key
        if self.user_id is not None:
            scoped_key = sha256(f"{self.user_id}:{dedupe_key}".encode()).hexdigest()
        record = TransactionRecord.from_draft(draft, scoped_key, user_id=self.user_id)
        self._session.add(record)
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
