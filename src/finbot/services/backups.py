from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from finbot.core.settings import Settings
from finbot.db.models import UserRecord
from finbot.services.user_dashboard_service import UserDashboardService


class SupabaseBackupService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def is_configured(self) -> bool:
        return bool(
            self._settings.supabase_url
            and self._settings.supabase_service_role_key
            and self._settings.supabase_backup_bucket
        )

    def backup_all_users(self, session: Session) -> int:
        if not self.is_configured:
            return 0
        users = list(session.scalars(select(UserRecord).where(UserRecord.telegram_user_id.is_not(None))))
        for user in users:
            csv_data = UserDashboardService(session, user.id).export_csv(None, None)
            self._upload(user.id, csv_data.encode("utf-8-sig"))
        return len(users)

    def _upload(self, user_id: str, content: bytes) -> None:
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d")
        path = f"daily/{timestamp}/{user_id}.csv"
        base_url = self._settings.supabase_url.rstrip("/")
        headers = {
            "Authorization": f"Bearer {self._settings.supabase_service_role_key}",
            "apikey": self._settings.supabase_service_role_key,
            "x-upsert": "true",
            "Content-Type": "text/csv; charset=utf-8",
        }
        response = httpx.put(
            f"{base_url}/storage/v1/object/{self._settings.supabase_backup_bucket}/{path}",
            headers=headers,
            content=content,
            timeout=httpx.Timeout(15.0, connect=3.0),
        )
        response.raise_for_status()
