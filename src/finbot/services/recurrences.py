from datetime import date

from finbot.db.models import RecurringTransactionRecord, TransactionRecord
from finbot.db.repositories import RecurringTransactionRepository
from finbot.models.transaction import TransactionDraft, TransactionStatus, TransactionType
from finbot.services.transactions import TransactionEntryService


class RecurringTransactionService:
    def __init__(
        self,
        repository: RecurringTransactionRepository,
        transaction_service: TransactionEntryService,
    ) -> None:
        self._repository = repository
        self._transaction_service = transaction_service

    def schedule_from_record(self, record: TransactionRecord) -> None:
        if not record.is_recurring:
            return
        self._repository.add(
            RecurringTransactionRecord(
                user_id=record.user_id or "",
                type=record.type,
                amount=record.amount,
                description=record.description,
                category=record.category,
                payment_method=record.payment_method,
                account_from=record.account_from,
                account_to=record.account_to,
                card_name=record.card_name,
                status=record.status,
                next_due_date=_add_months(record.transaction_date, 1),
            )
        )

    def generate_due(self, today: date | None = None) -> int:
        reference_date = today or date.today()
        generated = 0
        for schedule in self._repository.list_due(reference_date):
            draft = TransactionDraft(
                type=TransactionType(schedule.type),
                amount=schedule.amount,
                transaction_date=schedule.next_due_date,
                description=schedule.description,
                category=schedule.category,
                payment_method=schedule.payment_method,
                account_from=schedule.account_from,
                account_to=schedule.account_to,
                card_name=schedule.card_name,
                is_recurring=True,
                status=TransactionStatus(schedule.status),
                confidence=1.0,
            )
            result = self._transaction_service.record_draft(draft)
            if result.is_recorded:
                generated += 1
            schedule.next_due_date = _add_months(schedule.next_due_date, 1)
            if schedule.remaining_occurrences is not None:
                schedule.remaining_occurrences -= 1
                if schedule.remaining_occurrences <= 0:
                    schedule.is_active = False
        return generated


def _add_months(value: date, months: int) -> date:
    from finbot.services.transactions import _add_months as add_months

    return add_months(value, months)
