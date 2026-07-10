"""Scope account and card names by user."""

from alembic import op
from sqlalchemy import inspect

revision = "20260710_02"
down_revision = "20260710_01"
branch_labels = None
depends_on = None

NAMING_CONVENTION = {"uq": "uq_%(table_name)s_%(column_0_name)s"}


def _scope_name(table: str, composite_name: str) -> None:
    constraints = inspect(op.get_bind()).get_unique_constraints(table)
    has_global_name = any(item.get("column_names") == ["name"] for item in constraints)
    has_composite = any(
        item.get("column_names") == ["user_id", "name"] for item in constraints
    )
    if not has_global_name and has_composite:
        return
    with op.batch_alter_table(
        table,
        recreate="always",
        naming_convention=NAMING_CONVENTION,
    ) as batch_op:
        if has_global_name:
            batch_op.drop_constraint(f"uq_{table}_name", type_="unique")
        if not has_composite:
            batch_op.create_unique_constraint(composite_name, ["user_id", "name"])


def upgrade() -> None:
    tables = set(inspect(op.get_bind()).get_table_names())
    if "accounts" in tables:
        _scope_name("accounts", "uq_accounts_user_name")
    if "cards" in tables:
        _scope_name("cards", "uq_cards_user_name")


def downgrade() -> None:
    pass
