from decimal import Decimal

from finbot.db.models import TransactionRecord


TRANSACTION_HEADERS = (
    "ID",
    "Data",
    "Tipo",
    "Valor",
    "Categoria",
    "Forma de Pagamento",
    "Conta Origem",
    "Conta Destino",
    "Descricao",
    "Recorrente",
    "Status",
    "Confianca",
    "Chave Dedupe",
    "Criado Em",
)


def transaction_to_sheet_row(transaction: TransactionRecord) -> list[object]:
    return [
        transaction.id,
        transaction.transaction_date.isoformat(),
        transaction.type,
        _format_decimal(transaction.amount),
        transaction.category or "",
        transaction.payment_method or "",
        transaction.account_from or "",
        transaction.account_to or "",
        transaction.description,
        "sim" if transaction.is_recurring else "nao",
        transaction.status,
        _format_decimal(transaction.confidence),
        transaction.dedupe_key,
        transaction.created_at.isoformat(),
    ]


def _format_decimal(value: Decimal) -> str:
    return f"{value:.2f}"
