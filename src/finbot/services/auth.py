from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from finbot.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from finbot.core.settings import Settings
from finbot.db.models import RefreshTokenRecord, UserRecord
from finbot.db.repositories import UserRepository


class AuthenticationError(ValueError):
    pass


class AuthService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._users = UserRepository(session)

    def register(self, name: str, email: str, password: str) -> UserRecord:
        if self._users.get_by_email(email):
            raise AuthenticationError("email already registered")
        return self._users.add_web_user(name, email, hash_password(password))

    def authenticate(self, email: str, password: str) -> UserRecord:
        user = self._users.get_by_email(email)
        if (
            user is None
            or user.password_hash is None
            or user.status != "ACTIVE"
            or not verify_password(password, user.password_hash)
        ):
            raise AuthenticationError("invalid credentials")
        user.last_activity_at = datetime.now(UTC)
        return user

    def issue_tokens(self, user: UserRecord) -> tuple[str, str]:
        access = create_access_token(user.id, user.role, self._settings)
        refresh = create_refresh_token()
        self._session.add(
            RefreshTokenRecord(
                user_id=user.id,
                token_hash=hash_token(refresh),
                expires_at=datetime.now(UTC) + timedelta(days=self._settings.jwt_refresh_days),
            )
        )
        self._session.flush()
        return access, refresh

    def refresh(self, raw_token: str) -> tuple[UserRecord, str, str]:
        statement = select(RefreshTokenRecord).where(
            RefreshTokenRecord.token_hash == hash_token(raw_token)
        )
        token = self._session.scalars(statement).first()
        now = datetime.now(UTC)
        expires_at = token.expires_at if token else None
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if token is None or token.revoked_at is not None or expires_at is None or expires_at <= now:
            raise AuthenticationError("invalid refresh token")
        user = self._session.get(UserRecord, token.user_id)
        if user is None or user.status != "ACTIVE":
            raise AuthenticationError("invalid refresh token")
        token.revoked_at = now
        access, refresh = self.issue_tokens(user)
        return user, access, refresh

    def revoke(self, raw_token: str) -> None:
        statement = select(RefreshTokenRecord).where(
            RefreshTokenRecord.token_hash == hash_token(raw_token)
        )
        token = self._session.scalars(statement).first()
        if token is not None and token.revoked_at is None:
            token.revoked_at = datetime.now(UTC)


def bootstrap_admin(session: Session, settings: Settings) -> None:
    if not settings.admin_email or not settings.admin_password:
        return
    repository = UserRepository(session)
    if repository.get_by_email(settings.admin_email):
        return
    repository.add_web_user(
        name="Administrador",
        email=settings.admin_email,
        password_hash=hash_password(settings.admin_password),
        role="ADMIN",
    )
