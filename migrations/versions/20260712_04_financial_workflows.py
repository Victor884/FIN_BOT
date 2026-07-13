"""Add persisted Telegram workflows and financial scheduling fields."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

from finbot.db import models  # noqa: F401
from finbot.db.base import Base


revision = "20260712_04"
down_revision = "20260710_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # The project also supports SQLite locally, so using metadata with checkfirst
    # keeps the migration portable while Alembic owns the version boundary.
    for table_name in (
        "categories",
        "telegram_conversations",
        "recurring_transactions",
    ):
        Base.metadata.tables[table_name].create(bind, checkfirst=True)

    inspector = inspect(bind)
    if "transactions" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("transactions")}
    if "installment_group_id" not in existing:
        op.add_column("transactions", sa.Column("installment_group_id", sa.String(36), nullable=True))
    if "installment_number" not in existing:
        op.add_column("transactions", sa.Column("installment_number", sa.Integer(), nullable=True))
    if "installment_total" not in existing:
        op.add_column("transactions", sa.Column("installment_total", sa.Integer(), nullable=True))
    if "balance_applied" not in existing:
        op.add_column(
            "transactions",
            sa.Column("balance_applied", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    indexes = {item["name"] for item in inspector.get_indexes("transactions")}
    if "ix_transactions_user_date" not in indexes:
        op.create_index("ix_transactions_user_date", "transactions", ["user_id", "transaction_date"])
    if "ix_transactions_balance_applied" not in indexes:
        op.create_index("ix_transactions_balance_applied", "transactions", ["balance_applied"])
    if "ix_transactions_user_status_date" not in indexes:
        op.create_index(
            "ix_transactions_user_status_date", "transactions", ["user_id", "status", "transaction_date"]
        )


def downgrade() -> None:
    pass
