from datetime import UTC, date, datetime
from decimal import Decimal

from finbot.db.models import TransactionRecord
from finbot.services.queries import FinancialSummary
from finbot.sheets.dashboard import category_month_rows
from finbot.sheets.dashboard import dashboard_rows_from_summary
from finbot.sheets.dashboard import largest_expense_rows
from finbot.sheets.dashboard import monthly_summary_row
from finbot.sheets.dashboard import pending_rows


def make_record(description: str, amount: str, category: str = "alimentacao") -> TransactionRecord:
    return TransactionRecord(
        id=f"{description}-id",
        type="expense",
        amount=Decimal(amount),
        transaction_date=date(2026, 7, 9),
        description=description,
        category=category,
        payment_method="pix",
        account_from=None,
        account_to=None,
        is_recurring=False,
        status="pending",
        confidence=Decimal("0.850"),
        dedupe_key=f"{description}-dedupe",
        created_at=datetime(2026, 7, 9, 12, 0, tzinfo=UTC),
    )


def make_summary() -> FinancialSummary:
    internet = make_record("internet", "120", "moradia")
    mercado = make_record("mercado", "45", "alimentacao")
    return FinancialSummary(
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 31),
        total_income=Decimal("2500"),
        total_expenses=Decimal("165"),
        balance=Decimal("2335"),
        pending_total=Decimal("120"),
        expenses_by_category={
            "alimentacao": Decimal("45"),
            "moradia": Decimal("120"),
        },
        largest_expenses=(internet, mercado),
    )


def test_dashboard_rows_from_summary() -> None:
    rows = dashboard_rows_from_summary(make_summary())

    assert rows[0] == ["Receitas", "2500.00", "2026-07-01 a 2026-07-31", ""]
    assert rows[2] == ["Saldo", "2335.00", "2026-07-01 a 2026-07-31", "economia"]
    assert rows[4] == ["% Economia", "93.40", "2026-07-01 a 2026-07-31", ""]


def test_monthly_summary_row() -> None:
    assert monthly_summary_row(make_summary()) == [
        "2026-07",
        "2500.00",
        "165.00",
        "2335.00",
        "120.00",
        "2335.00",
        "93.40",
    ]


def test_category_month_rows() -> None:
    assert category_month_rows(make_summary()) == [
        ["2026-07", "alimentacao", "45.00", "27.27", "", ""],
        ["2026-07", "moradia", "120.00", "72.73", "", ""],
    ]


def test_pending_rows() -> None:
    rows = pending_rows([make_record("internet", "120", "moradia")])

    assert rows == [["2026-07-09", "120.00", "moradia", "internet", "pending"]]


def test_largest_expense_rows() -> None:
    rows = largest_expense_rows(make_summary())

    assert rows == [
        ["Maior despesa", "120.00", "2026-07-01 a 2026-07-31", "internet"],
        ["Maior despesa", "45.00", "2026-07-01 a 2026-07-31", "mercado"],
    ]
