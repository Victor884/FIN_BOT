from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finbot.api.schemas.dashboard import AdminSummaryData, CategoryPoint, IntegrationState, SeriesPoint
from finbot.core.settings import Settings
from finbot.db.models import (
    ApplicationErrorRecord,
    RequestMetricRecord,
    TelegramUpdateRecord,
    TransactionRecord,
    UserRecord,
)


class AdminDashboardService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    def summary(self, start_date: date, end_date: date) -> AdminSummaryData:
        start = datetime.combine(start_date, time.min, tzinfo=UTC)
        end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=UTC)
        user_count = int(self._session.scalar(select(func.count(UserRecord.id))) or 0)
        now = datetime.now(UTC)

        def active_since(days: int) -> int:
            threshold = now - timedelta(days=days)
            return int(
                self._session.scalar(
                    select(func.count(UserRecord.id)).where(UserRecord.last_activity_at >= threshold)
                )
                or 0
            )

        transactions = list(
            self._session.scalars(
                select(TransactionRecord).where(TransactionRecord.created_at >= start, TransactionRecord.created_at < end)
            )
        )
        updates = list(
            self._session.scalars(
                select(TelegramUpdateRecord).where(
                    TelegramUpdateRecord.created_at >= start, TelegramUpdateRecord.created_at < end
                )
            )
        )
        metrics = list(
            self._session.scalars(
                select(RequestMetricRecord).where(
                    RequestMetricRecord.created_at >= start, RequestMetricRecord.created_at < end
                )
            )
        )
        latencies = sorted(metric.duration_ms for metric in metrics)
        messages = len(updates)
        ai_messages = sum(1 for update in updates if update.ai_used)
        successful = sum(
            1 for update in updates if update.status not in {"invalid", "needs_more_info", "error"}
        )
        errors = sum(1 for metric in metrics if metric.status_code >= 400)
        income_amount = _transaction_amount(transactions, "income")
        expense_amount = _transaction_amount(transactions, "expense")
        return AdminSummaryData(
            users_total=user_count,
            users_active_today=active_since(1),
            users_active_7d=active_since(7),
            users_active_30d=active_since(30),
            new_users=int(
                self._session.scalar(
                    select(func.count(UserRecord.id)).where(
                        UserRecord.created_at >= start, UserRecord.created_at < end
                    )
                )
                or 0
            ),
            messages_total=messages,
            transactions_total=len(transactions),
            income_count=sum(1 for row in transactions if row.type == "income"),
            expense_count=sum(1 for row in transactions if row.type == "expense"),
            transfer_count=sum(1 for row in transactions if row.type == "transfer"),
            income_amount=income_amount,
            expense_amount=expense_amount,
            aggregate_balance=income_amount - expense_amount,
            local_parser_messages=messages - ai_messages,
            ai_parser_messages=ai_messages,
            ai_usage_rate=_rate(ai_messages, messages),
            parser_success_rate=_rate(successful, messages),
            error_rate=_rate(errors, len(metrics)),
            response_time_average_ms=(
                Decimal(str(sum(latencies) / len(latencies))).quantize(Decimal("0.01"))
                if latencies
                else Decimal("0")
            ),
            response_time_p50_ms=_percentile(latencies, 0.50),
            response_time_p95_ms=_percentile(latencies, 0.95),
            response_time_p99_ms=_percentile(latencies, 0.99),
            duplicates_blocked=sum(1 for update in updates if update.duplicate_blocked),
        )

    def daily_activity(self, start_date: date, end_date: date) -> list[dict[str, object]]:
        transaction_rows = self._daily_count(TransactionRecord, start_date, end_date)
        message_rows = self._daily_count(TelegramUpdateRecord, start_date, end_date)
        user_rows = self._daily_distinct_users(start_date, end_date)
        days = sorted(set(transaction_rows) | set(message_rows) | set(user_rows))
        return [
            {
                "date": day,
                "messages": message_rows.get(day, 0),
                "transactions": transaction_rows.get(day, 0),
                "active_users": user_rows.get(day, 0),
            }
            for day in days
        ]

    def activity(self, start_date: date, end_date: date) -> dict[str, object]:
        start = datetime.combine(start_date, time.min, tzinfo=UTC)
        end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=UTC)
        statement = (
            select(TelegramUpdateRecord, UserRecord)
            .outerjoin(UserRecord, UserRecord.id == TelegramUpdateRecord.user_id)
            .where(TelegramUpdateRecord.created_at >= start, TelegramUpdateRecord.created_at < end)
            .order_by(TelegramUpdateRecord.created_at.desc())
            .limit(50)
        )
        recent = [
            {
                "update_id": update.update_id,
                "user_id": update.user_id,
                "username": user.username if user else None,
                "status": update.status,
                "parser_source": update.parser_source,
                "ai_used": update.ai_used,
                "duration_ms": update.total_duration_ms,
                "created_at": update.created_at,
            }
            for update, user in self._session.execute(statement)
        ]
        return {"series": self.daily_activity(start_date, end_date), "recent": recent}

    def transaction_series(
        self,
        start_date: date,
        end_date: date,
        user_id: str | None = None,
        transaction_type: str | None = None,
        category: str | None = None,
        source: str | None = None,
        status: str | None = None,
    ) -> list[SeriesPoint]:
        filters = [TransactionRecord.transaction_date.between(start_date, end_date)]
        if user_id:
            filters.append(TransactionRecord.user_id == user_id)
        if transaction_type:
            filters.append(TransactionRecord.type == transaction_type)
        if category:
            filters.append(func.lower(TransactionRecord.category) == category.lower())
        if source:
            filters.append(TransactionRecord.source == source)
        if status:
            filters.append(TransactionRecord.status == status)
        rows = list(self._session.scalars(select(TransactionRecord).where(*filters)))
        by_day: dict[date, list[TransactionRecord]] = {}
        for row in rows:
            by_day.setdefault(row.transaction_date, []).append(row)
        return [
            SeriesPoint(
                label=day.isoformat(),
                income=_transaction_amount(values, "income"),
                expenses=_transaction_amount(values, "expense"),
                balance=_transaction_amount(values, "income")
                - _transaction_amount(values, "expense"),
                count=len(values),
            )
            for day, values in sorted(by_day.items())
        ]

    def categories(self, start_date: date, end_date: date) -> list[CategoryPoint]:
        statement = (
            select(
                func.coalesce(TransactionRecord.category, "Sem categoria"),
                func.sum(TransactionRecord.amount),
                func.count(TransactionRecord.id),
            )
            .where(TransactionRecord.transaction_date.between(start_date, end_date))
            .where(TransactionRecord.type == "expense")
            .group_by(TransactionRecord.category)
            .order_by(func.sum(TransactionRecord.amount).desc())
        )
        return [CategoryPoint(category=row[0], amount=row[1], count=row[2]) for row in self._session.execute(statement)]

    def performance(self, start_date: date, end_date: date) -> dict[str, object]:
        start = datetime.combine(start_date, time.min, tzinfo=UTC)
        end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=UTC)
        metrics = list(
            self._session.scalars(
                select(RequestMetricRecord)
                .where(RequestMetricRecord.created_at >= start, RequestMetricRecord.created_at < end)
                .order_by(RequestMetricRecord.created_at.desc())
            )
        )
        by_endpoint: dict[str, list[int]] = {}
        for metric in metrics:
            by_endpoint.setdefault(metric.endpoint, []).append(metric.duration_ms)
        endpoints = [
            {
                "endpoint": endpoint,
                "requests": len(values),
                "average_ms": round(sum(values) / len(values), 2),
                "p95_ms": _percentile(sorted(values), 0.95),
            }
            for endpoint, values in by_endpoint.items()
        ]
        endpoints.sort(key=lambda item: item["p95_ms"], reverse=True)
        return {"endpoints": endpoints, "recent_requests": [_metric_dict(row) for row in metrics[:50]]}

    def errors(self, start_date: date, end_date: date) -> list[dict[str, object]]:
        start = datetime.combine(start_date, time.min, tzinfo=UTC)
        end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=UTC)
        statement = (
            select(ApplicationErrorRecord)
            .where(ApplicationErrorRecord.created_at >= start, ApplicationErrorRecord.created_at < end)
            .order_by(ApplicationErrorRecord.created_at.desc())
            .limit(100)
        )
        return [
            {
                "id": row.id,
                "request_id": row.request_id,
                "endpoint": row.endpoint,
                "code": row.code,
                "integration": row.integration,
                "created_at": row.created_at,
            }
            for row in self._session.scalars(statement)
        ]

    def users(self, limit: int = 50) -> list[dict[str, object]]:
        statement = (
            select(UserRecord, func.count(TelegramUpdateRecord.update_id))
            .outerjoin(TelegramUpdateRecord, TelegramUpdateRecord.user_id == UserRecord.id)
            .group_by(UserRecord.id)
            .order_by(func.count(TelegramUpdateRecord.update_id).desc())
            .limit(limit)
        )
        return [
            {
                "id": user.id,
                "name": user.name,
                "username": user.username,
                "role": user.role,
                "status": user.status,
                "messages": messages,
                "created_at": user.created_at,
                "last_activity_at": user.last_activity_at,
            }
            for user, messages in self._session.execute(statement)
        ]

    def integrations(self) -> list[IntegrationState]:
        return [
            IntegrationState(name="api", status="available"),
            IntegrationState(name="database", status="available"),
            IntegrationState(
                name="telegram",
                status="configured" if self._settings.telegram_bot_token else "not_configured",
            ),
            IntegrationState(
                name="google_sheets",
                status=(
                    "configured"
                    if self._settings.google_sheets_spreadsheet_id
                    and self._settings.google_service_account_file
                    else "not_configured"
                ),
            ),
            IntegrationState(
                name="ai",
                status="enabled" if self._settings.ai_enabled else "disabled",
            ),
            IntegrationState(
                name="groq",
                status="configured" if self._settings.groq_api_key else "not_configured",
            ),
        ]

    def _daily_count(self, model, start_date: date, end_date: date) -> dict[str, int]:  # type: ignore[no-untyped-def]
        created_date = func.date(model.created_at)
        statement = (
            select(created_date, func.count())
            .where(created_date >= start_date.isoformat(), created_date <= end_date.isoformat())
            .group_by(created_date)
        )
        return {str(day): int(count) for day, count in self._session.execute(statement)}

    def _daily_distinct_users(self, start_date: date, end_date: date) -> dict[str, int]:
        created_date = func.date(TelegramUpdateRecord.created_at)
        statement = (
            select(created_date, func.count(func.distinct(TelegramUpdateRecord.user_id)))
            .where(created_date >= start_date.isoformat(), created_date <= end_date.isoformat())
            .group_by(created_date)
        )
        return {str(day): int(count) for day, count in self._session.execute(statement)}


def _transaction_amount(rows: list[TransactionRecord], transaction_type: str) -> Decimal:
    return sum((row.amount for row in rows if row.type == transaction_type), Decimal("0"))


def _rate(value: int, total: int) -> Decimal:
    if not total:
        return Decimal("0")
    return (Decimal(value) / Decimal(total) * 100).quantize(Decimal("0.01"))


def _percentile(values: list[int], percentile: float) -> int:
    if not values:
        return 0
    index = min(round((len(values) - 1) * percentile), len(values) - 1)
    return values[index]


def _metric_dict(metric: RequestMetricRecord) -> dict[str, object]:
    return {
        "request_id": metric.request_id,
        "endpoint": metric.endpoint,
        "method": metric.method,
        "status_code": metric.status_code,
        "duration_ms": metric.duration_ms,
        "origin": metric.origin,
        "created_at": metric.created_at,
    }
