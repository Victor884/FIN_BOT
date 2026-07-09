import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from finbot.db.models import AccountRecord
from finbot.db.repositories import AccountRepository
from finbot.models.account import AccountDraft, AccountType


ACCOUNT_ALIASES = {
    "banco inter": ("inter", "banco inter"),
    "nubank": ("nubank", "nu", "roxinho"),
    "mercado pago": ("mercado pago", "mp", "carteira do mercado pago"),
    "carteira fisica": ("carteira fisica", "dinheiro", "cash"),
    "poupanca": ("poupanca", "poupanca", "conta poupanca"),
    "investimentos": ("investimentos", "investimento", "reserva"),
    "conta corrente": ("conta corrente", "corrente", "conta principal"),
    "conta salario": ("conta salario", "salario"),
}

ACCOUNT_DISPLAY_NAMES = {
    "banco inter": "Banco Inter",
    "nubank": "Nubank",
    "mercado pago": "Mercado Pago",
    "carteira fisica": "Carteira fisica",
    "poupanca": "Poupanca",
    "investimentos": "Investimentos",
    "conta corrente": "Conta corrente",
    "conta salario": "Conta salario",
}


@dataclass(frozen=True)
class AccountResolution:
    account: AccountRecord | None
    canonical_name: str | None
    matches: tuple[AccountRecord, ...] = ()
    is_ambiguous: bool = False


@dataclass(frozen=True)
class AccountCreationParse:
    name: str | None
    account_type: AccountType | None
    initial_balance: Decimal | None
    missing_fields: tuple[str, ...] = ()


class AccountResolver:
    def __init__(self, repository: AccountRepository) -> None:
        self._repository = repository

    def resolve(self, text: str | None) -> AccountResolution:
        if not text:
            return AccountResolution(account=None, canonical_name=None)

        normalized = normalize_text(text)
        accounts = self._repository.list()
        direct_matches = [
            account for account in accounts if normalize_text(account.name) == normalized
        ]
        if len(direct_matches) == 1:
            account = direct_matches[0]
            return AccountResolution(account=account, canonical_name=account.name, matches=(account,))

        alias_name = self.canonical_name_for(normalized)
        if alias_name:
            existing = self._repository.get_by_name(alias_name)
            if existing:
                return AccountResolution(
                    account=existing, canonical_name=existing.name, matches=(existing,)
                )
            return AccountResolution(account=None, canonical_name=alias_name)

        partial_matches = [
            account
            for account in accounts
            if normalized in normalize_text(account.name) or normalize_text(account.name) in normalized
        ]
        if len(partial_matches) == 1:
            account = partial_matches[0]
            return AccountResolution(account=account, canonical_name=account.name, matches=(account,))
        if len(partial_matches) > 1:
            return AccountResolution(
                account=None,
                canonical_name=None,
                matches=tuple(partial_matches),
                is_ambiguous=True,
            )

        if "carteira digital" in normalized or normalized == "carteira":
            wallet_matches = [
                account for account in accounts if account.type in {AccountType.WALLET.value, "carteira"}
            ]
            if len(wallet_matches) == 1:
                account = wallet_matches[0]
                return AccountResolution(
                    account=account, canonical_name=account.name, matches=(account,)
                )
            if len(wallet_matches) > 1:
                return AccountResolution(
                    account=None,
                    canonical_name=None,
                    matches=tuple(wallet_matches),
                    is_ambiguous=True,
                )

        return AccountResolution(account=None, canonical_name=display_account_name(text))

    def canonical_name_for(self, text: str) -> str | None:
        normalized = normalize_text(text)
        for canonical, aliases in ACCOUNT_ALIASES.items():
            if normalized == canonical or any(alias in normalized for alias in aliases):
                return ACCOUNT_DISPLAY_NAMES[canonical]
        return None


class AccountService:
    def __init__(self, repository: AccountRepository) -> None:
        self._repository = repository
        self._resolver = AccountResolver(repository)

    def add_from_command(self, text: str) -> str:
        payload = text.removeprefix("/addconta").strip()
        if not payload:
            return "Informe nome, tipo e saldo. Exemplo: /addconta Banco Inter banco saldo 1000"

        match = re.search(
            r"^(?P<name>.+?)\s+(?P<type>banco|carteira|cartao|poupanca|poupança|investimento|outro)\s+saldo\s+(?P<balance>[\d.,]+)$",
            payload,
            flags=re.IGNORECASE,
        )
        if not match:
            return "Faltou algum dado. Use: /addconta Banco Inter banco saldo 1000"

        name = display_account_name(match.group("name"))
        account_type = parse_account_type(match.group("type"))
        balance = parse_decimal(match.group("balance"))
        if balance is None:
            return "Nao consegui entender o saldo inicial. Exemplo: saldo 1000"

        existing = self._repository.get_by_name(name)
        if existing:
            return f"A conta {existing.name} ja esta cadastrada com saldo {format_money(existing.current_balance)}."

        record = self._repository.add(
            AccountDraft(name=name, type=account_type, initial_balance=balance)
        )
        return f"Conta cadastrada: {record.name} com saldo {format_money(record.current_balance)}."

    def try_add_from_natural_text(self, text: str) -> str | None:
        parsed = parse_natural_account_creation(text)
        if parsed is None:
            return None

        if "name" in parsed.missing_fields:
            return "Qual e o nome da conta que voce quer cadastrar?"
        if "initial_balance" in parsed.missing_fields:
            account_name = parsed.name or "essa conta"
            return f"Qual e o saldo inicial da conta {account_name}?"

        if parsed.name is None or parsed.initial_balance is None:
            return "Nao consegui identificar todos os dados da conta. Envie nome e saldo inicial."

        account_type = parsed.account_type or infer_account_type(parsed.name)
        existing = self._repository.get_by_name(parsed.name)
        if existing:
            return f"A conta {existing.name} ja esta cadastrada com saldo {format_money(existing.current_balance)}."

        record = self._repository.add(
            AccountDraft(
                name=parsed.name,
                type=account_type,
                initial_balance=parsed.initial_balance,
            )
        )
        return f"Conta cadastrada: {record.name} com saldo {format_money(record.current_balance)}."

    def list_accounts(self) -> str:
        accounts = self._repository.list()
        if not accounts:
            return "Nenhuma conta cadastrada. Use /addconta Banco Inter banco saldo 1000."

        lines = ["Contas cadastradas:"]
        for account in accounts:
            lines.append(f"- {account.name}: {format_money(account.current_balance)}")
        total = sum((account.current_balance for account in accounts), Decimal("0"))
        lines.append("")
        lines.append(f"Saldo total: {format_money(total)}")
        return "\n".join(lines)

    def balance_message(self, account_text: str | None = None) -> str:
        if not account_text:
            total = sum(
                (account.current_balance for account in self._repository.list()),
                Decimal("0"),
            )
            return f"Saldo total: {format_money(total)}."

        resolution = self._resolver.resolve(account_text)
        if resolution.is_ambiguous:
            options = ", ".join(account.name for account in resolution.matches)
            return f"Encontrei mais de uma conta. Qual delas voce quer consultar? {options}."
        if resolution.account is None:
            return f"Nao encontrei a conta {display_account_name(account_text)}."
        return f"Saldo de {resolution.account.name}: {format_money(resolution.account.current_balance)}."

    @property
    def resolver(self) -> AccountResolver:
        return self._resolver


def normalize_text(text: str) -> str:
    lowered = text.strip().lower()
    normalized = unicodedata.normalize("NFKD", lowered)
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", ascii_text).strip()


def display_account_name(text: str) -> str:
    normalized = normalize_text(text)
    known = ACCOUNT_DISPLAY_NAMES.get(normalized)
    if known:
        return known
    return " ".join(part.capitalize() for part in normalized.split())


def parse_natural_account_creation(text: str) -> AccountCreationParse | None:
    normalized = normalize_text(text)
    if not _looks_like_account_creation(normalized):
        return None

    balance = _extract_money(normalized)
    explicit_type = _extract_explicit_account_type(normalized)
    name = _extract_account_name_from_creation(normalized)
    if name:
        canonical_name = AccountResolverStub.canonical_name_for(name) or display_account_name(name)
    else:
        canonical_name = None

    missing_fields: list[str] = []
    if not canonical_name:
        missing_fields.append("name")
    if balance is None:
        missing_fields.append("initial_balance")

    return AccountCreationParse(
        name=canonical_name,
        account_type=explicit_type or (infer_account_type(canonical_name) if canonical_name else None),
        initial_balance=balance,
        missing_fields=tuple(missing_fields),
    )


def _looks_like_account_creation(normalized_text: str) -> bool:
    triggers = (
        "crie uma conta",
        "criar conta",
        "adicionar conta",
        "adicione minha conta",
        "adicionar minha conta",
        "cadastrar carteira",
        "cadastrar conta",
        "tenho",
        "minha poupanca",
    )
    return any(trigger in normalized_text for trigger in triggers) and (
        "conta" in normalized_text
        or "carteira" in normalized_text
        or "poupanca" in normalized_text
        or "mercado pago" in normalized_text
    )


def _extract_account_name_from_creation(normalized_text: str) -> str | None:
    patterns = (
        r"conta chamada\s+(.+?)(?:\s+com\s+saldo|\s+saldo|$)",
        r"conta\s+(.+?)(?:\s+com\s+r\$|\s+com\s+\d|\s+tipo\s+|\s+saldo|$)",
        r"no\s+(.+?)(?:$|\s+com\s+saldo)",
        r"carteira\s+(.+?)(?:\s+com\s+saldo|\s+saldo|$)",
        r"minha\s+(.+?)\s+comeca\s+com",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized_text)
        if match:
            name = _clean_account_name(match.group(1))
            if name:
                return name
    if "minha poupanca" in normalized_text:
        return "poupanca"
    return None


def _clean_account_name(value: str) -> str:
    value = re.sub(r"\b(minha|meu|do|da|de|inicial|saldo|com|r\$)\b", " ", value)
    value = re.sub(r"\b\d[\d.,]*\b", " ", value)
    return normalize_text(value).strip(" ,-")


def _extract_explicit_account_type(normalized_text: str) -> AccountType | None:
    match = re.search(r"\btipo\s+(banco|carteira|cartao|poupanca|investimento|outro)\b", normalized_text)
    if match:
        return parse_account_type(match.group(1))
    return None


def _extract_money(normalized_text: str) -> Decimal | None:
    match = re.search(r"(?:r\$\s*)?(\d{1,3}(?:\.\d{3})+(?:,\d{2})?|\d+(?:[,.]\d{1,2})?)", normalized_text)
    if not match:
        return None
    return parse_decimal(match.group(1))


def infer_account_type(name: str) -> AccountType:
    normalized = normalize_text(name)
    if "poupanca" in normalized:
        return AccountType.SAVINGS
    if "invest" in normalized:
        return AccountType.INVESTMENT
    if "carteira" in normalized or normalized in {"mercado pago"}:
        return AccountType.WALLET
    if "cartao" in normalized:
        return AccountType.CARD
    if "banco" in normalized or normalized in {"nubank", "banco inter", "itau", "bradesco", "santander"}:
        return AccountType.BANK
    return AccountType.OTHER


class AccountResolverStub:
    @staticmethod
    def canonical_name_for(text: str) -> str | None:
        normalized = normalize_text(text)
        for canonical, aliases in ACCOUNT_ALIASES.items():
            if normalized == canonical or any(alias in normalized for alias in aliases):
                return ACCOUNT_DISPLAY_NAMES[canonical]
        return None


def parse_account_type(raw_type: str) -> AccountType:
    normalized = normalize_text(raw_type)
    if normalized == "poupanca":
        return AccountType.SAVINGS
    if normalized == "cartao":
        return AccountType.CARD
    if normalized == "investimento":
        return AccountType.INVESTMENT
    if normalized == "carteira":
        return AccountType.WALLET
    if normalized == "banco":
        return AccountType.BANK
    return AccountType.OTHER


def parse_decimal(value: str) -> Decimal | None:
    try:
        return Decimal(value.replace(".", "").replace(",", "."))
    except InvalidOperation:
        return None


def format_money(value: Decimal) -> str:
    return f"R$ {value:.2f}".replace(".", ",")
