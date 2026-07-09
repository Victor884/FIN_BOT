from datetime import date

from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from finbot.db.models import AccountRecord, CardRecord, TransactionRecord
from finbot.models.account import AccountDraft
from finbot.models.card import CardDraft
from finbot.models.transaction import TransactionDraft


class AccountRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, draft: AccountDraft) -> AccountRecord:
        record = AccountRecord.from_draft(draft)
        self._session.add(record)
        self._session.flush()
        return record

    def get(self, account_id: str) -> AccountRecord | None:
        return self._session.get(AccountRecord, account_id)

    def get_by_name(self, name: str) -> AccountRecord | None:
        statement: Select[tuple[AccountRecord]] = select(AccountRecord).where(
            func.lower(AccountRecord.name) == name.strip().lower()
        )
        return self._session.scalars(statement).first()

    def list(self, active_only: bool = True) -> list[AccountRecord]:
        statement: Select[tuple[AccountRecord]] = select(AccountRecord).order_by(
            AccountRecord.name.asc()
        )
        if active_only:
            statement = statement.where(AccountRecord.is_active.is_(True))
        return list(self._session.scalars(statement))

    def adjust_balance(self, account_id: str, amount_delta: Decimal) -> AccountRecord | None:
        record = self.get(account_id)
        if record is None:
            return None
        record.current_balance += amount_delta
        self._session.flush()
        return record


class CardRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, draft: CardDraft) -> CardRecord:
        record = CardRecord.from_draft(draft)
        self._session.add(record)
        self._session.flush()
        return record

    def get(self, card_id: str) -> CardRecord | None:
        return self._session.get(CardRecord, card_id)

    def get_by_name(self, name: str) -> CardRecord | None:
        statement: Select[tuple[CardRecord]] = select(CardRecord).where(
            func.lower(CardRecord.name) == name.strip().lower()
        )
        return self._session.scalars(statement).first()

    def list(self, active_only: bool = True) -> list[CardRecord]:
        statement: Select[tuple[CardRecord]] = select(CardRecord).order_by(CardRecord.name.asc())
        if active_only:
            statement = statement.where(CardRecord.is_active.is_(True))
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
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, draft: TransactionDraft, dedupe_key: str) -> TransactionRecord:
        record = TransactionRecord.from_draft(draft, dedupe_key)
        self._session.add(record)
        self._session.flush()
        return record

    def get(self, transaction_id: str) -> TransactionRecord | None:
        return self._session.get(TransactionRecord, transaction_id)

    def get_by_dedupe_key(self, dedupe_key: str) -> TransactionRecord | None:
        statement: Select[tuple[TransactionRecord]] = select(TransactionRecord).where(
            TransactionRecord.dedupe_key == dedupe_key
        )
        return self._session.scalars(statement).first()

    def list(self, limit: int = 100) -> list[TransactionRecord]:
        statement: Select[tuple[TransactionRecord]] = (
            select(TransactionRecord)
            .order_by(TransactionRecord.transaction_date.desc(), TransactionRecord.created_at.desc())
            .limit(limit)
        )
        return list(self._session.scalars(statement))

    def list_between(self, start_date: date, end_date: date) -> list[TransactionRecord]:
        statement: Select[tuple[TransactionRecord]] = (
            select(TransactionRecord)
            .where(TransactionRecord.transaction_date >= start_date)
            .where(TransactionRecord.transaction_date <= end_date)
            .order_by(TransactionRecord.transaction_date.asc(), TransactionRecord.created_at.asc())
        )
        return list(self._session.scalars(statement))

    def list_pending(self) -> list[TransactionRecord]:
        statement: Select[tuple[TransactionRecord]] = (
            select(TransactionRecord)
            .where(TransactionRecord.status == "pending")
            .order_by(TransactionRecord.transaction_date.asc(), TransactionRecord.created_at.asc())
        )
        return list(self._session.scalars(statement))

    def list_by_account(self, account_name: str, limit: int = 100) -> list[TransactionRecord]:
        statement: Select[tuple[TransactionRecord]] = (
            select(TransactionRecord)
            .where(
                (TransactionRecord.account_from == account_name)
                | (TransactionRecord.account_to == account_name)
            )
            .order_by(TransactionRecord.transaction_date.desc(), TransactionRecord.created_at.desc())
            .limit(limit)
        )
        return list(self._session.scalars(statement))
