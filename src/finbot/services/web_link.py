import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from finbot.core.security import hash_password, hash_token
from finbot.db.models import UserRecord, WebLinkCodeRecord


class WebLinkError(ValueError):
    pass


class WebLinkService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_code(self, user_id: str) -> str:
        code = secrets.token_urlsafe(12)
        self._session.add(
            WebLinkCodeRecord(
                user_id=user_id,
                code_hash=hash_token(code),
                expires_at=datetime.now(UTC) + timedelta(minutes=10),
            )
        )
        self._session.flush()
        return code

    def exchange(self, code: str, email: str, password: str, name: str | None) -> UserRecord:
        statement = select(WebLinkCodeRecord).where(WebLinkCodeRecord.code_hash == hash_token(code))
        link = self._session.scalars(statement).first()
        now = datetime.now(UTC)
        expires_at = link.expires_at if link else None
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if link is None or link.used_at is not None or expires_at is None or expires_at <= now:
            raise WebLinkError("invalid or expired link code")
        existing = self._session.scalars(
            select(UserRecord).where(UserRecord.email == email.strip().lower())
        ).first()
        if existing is not None and existing.id != link.user_id:
            raise WebLinkError("email already registered")
        user = self._session.get(UserRecord, link.user_id)
        if user is None or user.status != "ACTIVE":
            raise WebLinkError("user not available")
        user.email = email.strip().lower()
        user.password_hash = hash_password(password)
        user.name = name.strip() if name else user.name
        link.used_at = now
        self._session.flush()
        return user
