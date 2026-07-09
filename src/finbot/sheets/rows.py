from decimal import Decimal

from finbot.db.models import TransactionRecord


TRANSACTION_HEADERS = (
    "ID",
    "Data",
    "Tipo",
    "Descricao",
    "Categoria",
    "Valor",
    "Conta Origem",
    "Conta Destino",
    "Conta Principal",
    "Cartao",
    "Forma de Pagamento",
    "Status",
    "Mes",
    "Ano",
    "Observacao",
    "Criado Em",
    "Atualizado Em",
)


def transaction_to_sheet_row(transaction: TransactionRecord) -> list[object]:
    return [
        transaction.id,
        transaction.transaction_date.isoformat(),
        transaction.type,
        transaction.description,
        transaction.category or "",
        _format_decimal(transaction.amount),
        transaction.account_from or "",
        transaction.account_to or "",
        transaction.account_from or transaction.account_to or "",
        transaction.card_name or "",
        transaction.payment_method or "",
        transaction.status,
        transaction.transaction_date.strftime("%Y-%m"),
        transaction.transaction_date.year,
        "recorrente" if transaction.is_recurring else "",
        transaction.created_at.isoformat(),
        transaction.created_at.isoformat(),
    ]


def _format_decimal(value: Decimal) -> str:
    return f"{value:.2f}"
