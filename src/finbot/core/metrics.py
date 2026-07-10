from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from finbot.db.models import ApplicationErrorRecord, RequestMetricRecord, TelegramUpdateRecord


def apply_retention_policy(session: Session, retention_days: int) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=max(retention_days, 1))
    deleted = 0
    for model in (RequestMetricRecord, ApplicationErrorRecord, TelegramUpdateRecord):
        result = session.execute(delete(model).where(model.created_at < cutoff))
        deleted += int(result.rowcount or 0)
    return deleted
