from datetime import date

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from finbot.db.models import TransactionRecord
from finbot.models.transaction import TransactionDraft


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
