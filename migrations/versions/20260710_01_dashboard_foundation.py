"""Add ownership, synchronization and dashboard telemetry fields."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260710_01"
down_revision = None
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table)}


def _add_column(table: str, column: sa.Column) -> None:
    if column.name not in _columns(table):
        op.add_column(table, column)


def _add_index(name: str, table: str, columns: list[str]) -> None:
    indexes = {index["name"] for index in inspect(op.get_bind()).get_indexes(table)}
    if name not in indexes:
        op.create_index(name, table, columns, unique=False)


def upgrade() -> None:
    tables = set(inspect(op.get_bind()).get_table_names())
    if "accounts" in tables:
        _add_column("accounts", sa.Column("user_id", sa.String(36), nullable=True))
        _add_index("ix_accounts_user_id", "accounts", ["user_id"])
    if "cards" in tables:
        _add_column("cards", sa.Column("user_id", sa.String(36), nullable=True))
        _add_index("ix_cards_user_id", "cards", ["user_id"])
    if "transactions" in tables:
        _add_column("transactions", sa.Column("user_id", sa.String(36), nullable=True))
        _add_column("transactions", sa.Column("card_name", sa.String(120), nullable=True))
        _add_column(
            "transactions",
            sa.Column("source", sa.String(20), nullable=False, server_default="telegram"),
        )
        _add_column(
            "transactions",
            sa.Column("sheets_synced", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        _add_column(
            "transactions",
            sa.Column("needs_confirmation", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        _add_index("ix_transactions_user_id", "transactions", ["user_id"])
        _add_index("ix_transactions_source", "transactions", ["source"])
        _add_index("ix_transactions_sheets_synced", "transactions", ["sheets_synced"])
        _add_index("ix_transactions_needs_confirmation", "transactions", ["needs_confirmation"])


def downgrade() -> None:
    # Ownership columns are intentionally retained to avoid destructive data loss.
    pass
