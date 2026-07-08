from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from finbot.db.models import TransactionRecord
from finbot.models.transaction import TransactionDraft


class TransactionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, draft: TransactionDraft) -> TransactionRecord:
        record = TransactionRecord.from_draft(draft)
        self._session.add(record)
        self._session.flush()
        return record

    def get(self, transaction_id: str) -> TransactionRecord | None:
        return self._session.get(TransactionRecord, transaction_id)

    def list(self, limit: int = 100) -> list[TransactionRecord]:
        statement: Select[tuple[TransactionRecord]] = (
            select(TransactionRecord)
            .order_by(TransactionRecord.transaction_date.desc(), TransactionRecord.created_at.desc())
            .limit(limit)
        )
        return list(self._session.scalars(statement))

