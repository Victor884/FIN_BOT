import csv
import io
import math
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from finbot.api.schemas.dashboard import (
    CategoryPoint,
    FinancialSummaryData,
    SeriesPoint,
    TransactionItem,
    TransactionPage,
)
from finbot.db.models import TransactionRecord


class UserDashboardService:
    def __init__(self, session: Session, user_id: str) -> None:
        self._session = session
        self._user_id = user_id

    def summary(self, start_date: date, end_date: date) -> FinancialSummaryData:
        rows = self._records_between(start_date, end_date)
        income = _sum_type(rows, "income")
        expenses = _sum_type(rows, "expense")
        expense_rows = [row for row in rows if row.type == "expense"]
        days = max((end_date - start_date).days + 1, 1)
        category_totals: dict[str, Decimal] = {}
        for row in expense_rows:
            category = row.category or "Sem categoria"
            category_totals[category] = category_totals.get(category, Decimal("0")) + row.amount
        top_category = max(category_totals, key=category_totals.get) if category_totals else None

        period_days = (end_date - start_date).days + 1
        previous_end = start_date - timedelta(days=1)
        previous_start = previous_end - timedelta(days=period_days - 1)
        previous = self._records_between(previous_start, previous_end)
        previous_balance = _sum_type(previous, "income") - _sum_type(previous, "expense")
        balance = income - expenses
        change = None
        if previous_balance:
            change = ((balance - previous_balance) / abs(previous_balance) * 100).quantize(
                Decimal("0.01")
            )

        return FinancialSummaryData(
            start_date=start_date,
            end_date=end_date,
            income=income,
            expenses=expenses,
            balance=balance,
            transaction_count=len(rows),
            daily_expense_average=(expenses / days).quantize(Decimal("0.01")),
            largest_expense=max((row.amount for row in expense_rows), default=Decimal("0")),
            top_expense_category=top_category,
            pending_expenses=sum(
                (row.amount for row in expense_rows if row.status == "pending"), Decimal("0")
            ),
            previous_period_balance=previous_balance,
            balance_change_percent=change,
        )

    def cash_flow(self, start_date: date, end_date: date) -> list[SeriesPoint]:
        totals: dict[date, dict[str, Decimal | int]] = {}
        for row in self._records_between(start_date, end_date):
            point = totals.setdefault(
                row.transaction_date,
                {"income": Decimal("0"), "expenses": Decimal("0"), "count": 0},
            )
            if row.type == "income":
                point["income"] += row.amount  # type: ignore[operator]
            elif row.type == "expense":
                point["expenses"] += row.amount  # type: ignore[operator]
            point["count"] += 1  # type: ignore[operator]
        return [
            SeriesPoint(
                label=day.isoformat(),
                income=values["income"],
                expenses=values["expenses"],
                balance=values["income"] - values["expenses"],  # type: ignore[operator]
                count=values["count"],
            )
            for day, values in sorted(totals.items())
        ]

    def categories(self, start_date: date, end_date: date) -> list[CategoryPoint]:
        statement = (
            select(
                func.coalesce(TransactionRecord.category, "Sem categoria"),
                func.sum(TransactionRecord.amount),
                func.count(TransactionRecord.id),
            )
            .where(TransactionRecord.user_id == self._user_id)
            .where(TransactionRecord.type == "expense")
            .where(TransactionRecord.transaction_date.between(start_date, end_date))
            .group_by(TransactionRecord.category)
            .order_by(func.sum(TransactionRecord.amount).desc())
        )
        return [
            CategoryPoint(category=row[0], amount=row[1], count=row[2])
            for row in self._session.execute(statement)
        ]

    def transactions(
        self,
        *,
        page: int,
        page_size: int,
        start_date: date | None = None,
        end_date: date | None = None,
        category: str | None = None,
        transaction_type: str | None = None,
        search: str | None = None,
        status: str | None = None,
        sort: str = "date_desc",
    ) -> TransactionPage:
        filters = [TransactionRecord.user_id == self._user_id]
        if start_date:
            filters.append(TransactionRecord.transaction_date >= start_date)
        if end_date:
            filters.append(TransactionRecord.transaction_date <= end_date)
        if category:
            filters.append(func.lower(TransactionRecord.category) == category.lower())
        if transaction_type:
            filters.append(TransactionRecord.type == transaction_type)
        if status:
            filters.append(TransactionRecord.status == status)
        if search:
            filters.append(TransactionRecord.description.ilike(f"%{search[:100]}%"))

        count_statement = select(func.count(TransactionRecord.id)).where(*filters)
        total = int(self._session.scalar(count_statement) or 0)
        order = {
            "date_asc": (TransactionRecord.transaction_date.asc(), TransactionRecord.created_at.asc()),
            "amount_desc": (TransactionRecord.amount.desc(), TransactionRecord.created_at.desc()),
            "amount_asc": (TransactionRecord.amount.asc(), TransactionRecord.created_at.desc()),
        }.get(sort, (TransactionRecord.transaction_date.desc(), TransactionRecord.created_at.desc()))
        statement: Select[tuple[TransactionRecord]] = (
            select(TransactionRecord)
            .where(*filters)
            .order_by(*order)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [_to_item(record) for record in self._session.scalars(statement)]
        return TransactionPage(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            pages=math.ceil(total / page_size) if total else 0,
        )

    def get_transaction(self, transaction_id: str) -> TransactionItem | None:
        statement = select(TransactionRecord).where(
            TransactionRecord.id == transaction_id,
            TransactionRecord.user_id == self._user_id,
        )
        record = self._session.scalars(statement).first()
        return _to_item(record) if record else None

    def export_csv(self, start_date: date | None, end_date: date | None) -> str:
        page = self.transactions(
            page=1, page_size=10_000, start_date=start_date, end_date=end_date, sort="date_asc"
        )
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "data", "tipo", "descricao", "categoria", "valor", "status"])
        for item in page.items:
            writer.writerow(
                [
                    item.id,
                    item.transaction_date.isoformat(),
                    item.type,
                    item.description,
                    item.category or "",
                    str(item.amount),
                    item.status,
                ]
            )
        return output.getvalue()

    def _records_between(self, start_date: date, end_date: date) -> list[TransactionRecord]:
        statement = select(TransactionRecord).where(
            TransactionRecord.user_id == self._user_id,
            TransactionRecord.transaction_date.between(start_date, end_date),
        )
        return list(self._session.scalars(statement))


def _sum_type(rows: list[TransactionRecord], transaction_type: str) -> Decimal:
    return sum((row.amount for row in rows if row.type == transaction_type), Decimal("0"))


def _to_item(record: TransactionRecord) -> TransactionItem:
    return TransactionItem(
        id=record.id,
        type=record.type,
        amount=record.amount,
        transaction_date=record.transaction_date,
        description=record.description,
        category=record.category,
        account_from=record.account_from,
        account_to=record.account_to,
        payment_method=record.payment_method,
        status=record.status,
        source=record.source,
        sheets_synced=record.sheets_synced,
        needs_confirmation=record.needs_confirmation,
        is_recurring=record.is_recurring,
        installment_group_id=record.installment_group_id,
        installment_number=record.installment_number,
        installment_total=record.installment_total,
        created_at=record.created_at,
    )
