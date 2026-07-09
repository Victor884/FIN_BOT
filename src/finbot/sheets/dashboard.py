from datetime import date
from decimal import Decimal

from finbot.db.models import TransactionRecord
from finbot.services.queries import FinancialSummary


DASHBOARD_HEADERS = ("Indicador", "Valor", "Periodo", "Observacao")
MONTHLY_SUMMARY_HEADERS = (
    "Mes",
    "Receitas",
    "Despesas",
    "Saldo",
    "Pendentes",
    "Economia",
    "% Economia",
)
CATEGORY_MONTH_HEADERS = ("Mes", "Categoria", "Total", "% do Orcamento", "Limite", "Diferenca")
PENDING_HEADERS = ("Data", "Valor", "Categoria", "Descricao", "Status")


def dashboard_rows_from_summary(summary: FinancialSummary) -> list[list[object]]:
    period = _format_period(summary.start_date, summary.end_date)
    savings_rate = _safe_percentage(summary.balance, summary.total_income)
    deficit_or_savings = "economia" if summary.balance >= 0 else "deficit"

    return [
        ["Receitas", _format_decimal(summary.total_income), period, ""],
        ["Despesas", _format_decimal(summary.total_expenses), period, ""],
        ["Saldo", _format_decimal(summary.balance), period, deficit_or_savings],
        ["Pendentes", _format_decimal(summary.pending_total), period, ""],
        ["% Economia", _format_decimal(savings_rate), period, ""],
    ]


def monthly_summary_row(summary: FinancialSummary) -> list[object]:
    return [
        summary.start_date.strftime("%Y-%m"),
        _format_decimal(summary.total_income),
        _format_decimal(summary.total_expenses),
        _format_decimal(summary.balance),
        _format_decimal(summary.pending_total),
        _format_decimal(max(summary.balance, Decimal("0"))),
        _format_decimal(_safe_percentage(summary.balance, summary.total_income)),
    ]


def category_month_rows(summary: FinancialSummary) -> list[list[object]]:
    month = summary.start_date.strftime("%Y-%m")
    total_expenses = summary.total_expenses
    return [
        [
            month,
            category,
            _format_decimal(total),
            _format_decimal(_safe_percentage(total, total_expenses)),
            "",
            "",
        ]
        for category, total in sorted(summary.expenses_by_category.items())
    ]


def pending_rows(records: list[TransactionRecord]) -> list[list[object]]:
    return [
        [
            record.transaction_date.isoformat(),
            _format_decimal(record.amount),
            record.category or "",
            record.description,
            record.status,
        ]
        for record in records
    ]


def largest_expense_rows(summary: FinancialSummary) -> list[list[object]]:
    period = _format_period(summary.start_date, summary.end_date)
    return [
        [
            "Maior despesa",
            _format_decimal(record.amount),
            period,
            record.description,
        ]
        for record in summary.largest_expenses
    ]


def _safe_percentage(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == 0:
        return Decimal("0")
    return (numerator / denominator * Decimal("100")).quantize(Decimal("0.01"))


def _format_period(start_date: date, end_date: date) -> str:
    return f"{start_date.isoformat()} a {end_date.isoformat()}"


def _format_decimal(value: Decimal) -> str:
    return f"{value:.2f}"
