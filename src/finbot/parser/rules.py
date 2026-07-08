import re
import unicodedata
from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from finbot.models.transaction import TransactionDraft, TransactionStatus, TransactionType
from finbot.parser.contracts import ParseResult


VALUE_PATTERN = re.compile(
    r"(?:r\$\s*)?(\d{1,3}(?:\.\d{3})+(?:,\d{2})?|\d+(?:[,.]\d{1,2})?)",
    re.IGNORECASE,
)

EXPENSE_KEYWORDS = ("gastei", "paguei", "pagar", "comprei", "despesa", "pagamento")
INCOME_KEYWORDS = ("recebi", "ganhei", "salario", "renda", "deposito")
TRANSFER_KEYWORDS = ("transferi", "transferencia", "enviei")
PENDING_KEYWORDS = ("vou pagar", "pendente", "a pagar", "vencimento", "vence")
RECURRING_KEYWORDS = ("todo mes", "mensal", "recorrente", "fixo", "fixa")

CATEGORY_ALIASES = {
    "alimentacao": ("mercado", "supermercado", "restaurante", "lanche", "comida", "padaria"),
    "transporte": ("uber", "99", "onibus", "metro", "combustivel", "gasolina"),
    "moradia": ("aluguel", "condominio", "internet", "luz", "energia", "agua"),
    "saude": ("farmacia", "medico", "consulta", "remedio"),
    "educacao": ("curso", "faculdade", "livro", "escola"),
    "lazer": ("cinema", "show", "bar", "viagem", "jogo"),
    "salario": ("salario", "pagamento do trabalho"),
    "investimentos": ("dividendo", "rendimento", "investimento", "cdb", "tesouro"),
}

PAYMENT_METHOD_ALIASES = {
    "pix": ("pix",),
    "cartao_credito": ("cartao de credito", "credito"),
    "cartao_debito": ("cartao de debito", "debito"),
    "dinheiro": ("dinheiro", "cash"),
    "transferencia_bancaria": ("transferencia", "ted", "doc"),
}


class RuleBasedParser:
    def __init__(self, today_provider: Callable[[], date] | None = None) -> None:
        self._today_provider = today_provider or date.today

    def parse(self, text: str) -> ParseResult:
        normalized_text = _normalize(text)
        transaction_type = _detect_transaction_type(normalized_text)
        amount = _extract_amount(normalized_text)
        transaction_date = self._extract_date(normalized_text)

        missing_fields = []
        if transaction_type is None:
            missing_fields.append("type")
        if amount is None:
            missing_fields.append("amount")

        if missing_fields:
            return ParseResult(draft=None, missing_fields=tuple(missing_fields), raw_text=text)

        category = _detect_category(normalized_text)
        payment_method = _detect_payment_method(normalized_text)
        account_from, account_to = _extract_transfer_accounts(normalized_text, transaction_type)
        description = _build_description(normalized_text, amount)
        status = _detect_status(normalized_text, transaction_type)
        is_recurring = any(keyword in normalized_text for keyword in RECURRING_KEYWORDS)

        draft = TransactionDraft(
            type=transaction_type,
            amount=amount,
            transaction_date=transaction_date,
            description=description,
            category=category,
            payment_method=payment_method,
            account_from=account_from,
            account_to=account_to,
            is_recurring=is_recurring,
            status=status,
            confidence=0.85,
        )
        return ParseResult(draft=draft, raw_text=text, needs_confirmation=False)

    def _extract_date(self, normalized_text: str) -> date:
        today = self._today_provider()
        if "ontem" in normalized_text:
            return today - timedelta(days=1)
        return today


def _normalize(text: str) -> str:
    lowered = text.strip().lower()
    normalized = unicodedata.normalize("NFKD", lowered)
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", ascii_text)


def _detect_transaction_type(normalized_text: str) -> TransactionType | None:
    if any(keyword in normalized_text for keyword in TRANSFER_KEYWORDS):
        return TransactionType.TRANSFER
    if any(keyword in normalized_text for keyword in INCOME_KEYWORDS):
        return TransactionType.INCOME
    if any(keyword in normalized_text for keyword in EXPENSE_KEYWORDS):
        return TransactionType.EXPENSE
    return None


def _extract_amount(normalized_text: str) -> Decimal | None:
    match = VALUE_PATTERN.search(normalized_text)
    if not match:
        return None

    raw_value = match.group(1)
    decimal_value = raw_value.replace(".", "").replace(",", ".")
    try:
        return Decimal(decimal_value)
    except InvalidOperation:
        return None


def _detect_category(normalized_text: str) -> str | None:
    for category, aliases in CATEGORY_ALIASES.items():
        if any(alias in normalized_text for alias in aliases):
            return category
    return None


def _detect_payment_method(normalized_text: str) -> str | None:
    for payment_method, aliases in PAYMENT_METHOD_ALIASES.items():
        if any(alias in normalized_text for alias in aliases):
            return payment_method
    return None


def _extract_transfer_accounts(
    normalized_text: str, transaction_type: TransactionType
) -> tuple[str | None, str | None]:
    if transaction_type != TransactionType.TRANSFER:
        return None, None

    match = re.search(r"\b(?:da|de)\s+(.+?)\s+para\s+(?:a\s+|o\s+)?(.+)$", normalized_text)
    if not match:
        return None, None

    account_from = _clean_fragment(match.group(1))
    account_to = _clean_fragment(match.group(2))
    return account_from or None, account_to or None


def _detect_status(normalized_text: str, transaction_type: TransactionType) -> TransactionStatus:
    if any(keyword in normalized_text for keyword in PENDING_KEYWORDS):
        return TransactionStatus.PENDING
    if transaction_type == TransactionType.INCOME:
        return TransactionStatus.RECEIVED
    return TransactionStatus.PAID


def _build_description(normalized_text: str, amount: Decimal) -> str:
    without_amount = VALUE_PATTERN.sub("", normalized_text, count=1)
    without_currency = without_amount.replace("r$", "")

    for token in (
        *EXPENSE_KEYWORDS,
        *INCOME_KEYWORDS,
        *TRANSFER_KEYWORDS,
        "hoje",
        "ontem",
        "no",
        "na",
        "de",
        "do",
        "da",
        "com",
    ):
        without_currency = re.sub(rf"\b{re.escape(_normalize(token))}\b", " ", without_currency)

    description = _clean_fragment(without_currency)
    return description or f"movimentacao {amount}"


def _clean_fragment(value: str) -> str:
    value = re.sub(r"\b(hoje|ontem|pix|cartao|cartao de credito|cartao de debito)\b", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" .,-")
