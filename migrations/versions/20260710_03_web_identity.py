"""Ensure web identity and telemetry tables exist."""

from alembic import op

from finbot.db.base import Base
from finbot.db import models  # noqa: F401

revision = "20260710_03"
down_revision = "20260710_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for table_name in (
        "users",
        "telegram_updates",
        "request_metrics",
        "application_errors",
        "refresh_tokens",
        "web_link_codes",
    ):
        Base.metadata.tables[table_name].create(bind, checkfirst=True)


def downgrade() -> None:
    pass
