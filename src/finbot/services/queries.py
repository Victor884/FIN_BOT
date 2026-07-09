from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from finbot.db.models import TransactionRecord
from finbot.db.repositories import TransactionRepository
from finbot.models.transaction import TransactionStatus, TransactionType


@dataclass(frozen=True)
class FinancialSummary:
    start_date: date
    end_date: date
    total_income: Decimal
    total_expenses: Decimal
    balance: Decimal
    pending_total: Decimal
    expenses_by_category: dict[str, Decimal]
    largest_expenses: tuple[TransactionRecord, ...]


class FinancialQueryService:
    def __init__(self, repository: TransactionRepository) -> None:
        self._repository = repository

    def monthly_summary(self, year: int, month: int) -> FinancialSummary:
        start_date = date(year, month, 1)
        end_date = _month_end(year, month)
        return self.summary_between(start_date, end_date)

    def weekly_summary(self, reference_date: date) -> FinancialSummary:
        start_date = reference_date - timedelta(days=reference_date.weekday())
        end_date = start_date + timedelta(days=6)
        return self.summary_between(start_date, end_date)

    def total_expenses_by_category(
        self, category: str, start_date: date, end_date: date
    ) -> Decimal:
        normalized_category = category.strip().lower()
        records = self._repository.list_between(start_date, end_date)
        return sum(
            (
                record.amount
                for record in records
                if record.type == TransactionType.EXPENSE.value
                and (record.category or "").lower() == normalized_category
            ),
            Decimal("0"),
        )

    def pending_transactions(self) -> list[TransactionRecord]:
        return self._repository.list_pending()

    def summary_between(self, start_date: date, end_date: date) -> FinancialSummary:
        records = self._repository.list_between(start_date, end_date)
        income_records = _records_by_type(records, TransactionType.INCOME)
        expense_records = _records_by_type(records, TransactionType.EXPENSE)
        pending_records = [
            record for record in records if record.status == TransactionStatus.PENDING.value
        ]

        total_income = _sum_amounts(income_records)
        total_expenses = _sum_amounts(expense_records)

        return FinancialSummary(
            start_date=start_date,
            end_date=end_date,
            total_income=total_income,
            total_expenses=total_expenses,
            balance=total_income - total_expenses,
            pending_total=_sum_amounts(pending_records),
            expenses_by_category=_expenses_by_category(expense_records),
            largest_expenses=tuple(
                sorted(expense_records, key=lambda record: record.amount, reverse=True)[:5]
            ),
        )


def _month_end(year: int, month: int) -> date:
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1) - timedelta(days=1)


def _records_by_type(
    records: list[TransactionRecord], transaction_type: TransactionType
) -> list[TransactionRecord]:
    return [record for record in records if record.type == transaction_type.value]


def _sum_amounts(records: list[TransactionRecord]) -> Decimal:
    return sum((record.amount for record in records), Decimal("0"))


def _expenses_by_category(records: list[TransactionRecord]) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {}
    for record in records:
        category = record.category or "sem_categoria"
        totals[category] = totals.get(category, Decimal("0")) + record.amount
    return totals
