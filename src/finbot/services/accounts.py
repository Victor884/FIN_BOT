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
