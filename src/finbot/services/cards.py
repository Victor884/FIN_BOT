import re
from dataclasses import dataclass
from decimal import Decimal

from finbot.db.models import AccountRecord, CardRecord
from finbot.db.repositories import AccountRepository, CardRepository
from finbot.models.card import CardDraft, CardType
from finbot.services.accounts import AccountResolver, display_account_name, format_money, parse_decimal


@dataclass(frozen=True)
class CardResolution:
    card: CardRecord | None
    matches: tuple[CardRecord, ...] = ()
    is_ambiguous: bool = False


class CardResolver:
    def __init__(self, repository: CardRepository) -> None:
        self._repository = repository

    def resolve(self, text: str | None) -> CardResolution:
        if not text:
            return CardResolution(card=None)
        normalized = _normalize_card_text(text)
        matches = [
            card
            for card in self._repository.list()
            if normalized in _normalize_card_text(card.name)
            or _normalize_card_text(card.name) in normalized
        ]
        if len(matches) == 1:
            return CardResolution(card=matches[0], matches=(matches[0],))
        if len(matches) > 1:
            return CardResolution(card=None, matches=tuple(matches), is_ambiguous=True)
        return CardResolution(card=None)


class CardService:
    def __init__(
        self,
        card_repository: CardRepository,
        account_repository: AccountRepository,
    ) -> None:
        self._card_repository = card_repository
        self._account_repository = account_repository
        self._account_resolver = AccountResolver(account_repository)
        self._card_resolver = CardResolver(card_repository)

    def add_from_command(self, text: str) -> str:
        payload = text.removeprefix("/addcartao").strip()
        if not payload:
            return (
                "Informe nome, tipo e conta. Exemplo: "
                "/addcartao Nubank credito conta Nubank limite 2000"
            )
        return self._add_from_text(payload)

    def try_add_from_natural_text(self, text: str) -> str | None:
        normalized = _normalize_card_text(text)
        if "cartao" not in normalized or not any(
            trigger in normalized for trigger in ("criar", "adicionar", "cadastrar")
        ):
            return None
        return self._add_from_text(text)

    def list_cards(self) -> str:
        cards = self._card_repository.list()
        if not cards:
            return "Nenhum cartao cadastrado. Use /addcartao Nubank credito conta Nubank limite 2000."
        lines = ["Cartoes cadastrados:"]
        for card in cards:
            account = self._linked_account(card)
            account_label = account.name if account else "sem conta vinculada"
            extra = f" - fatura {format_money(card.current_invoice)}"
            if card.type == CardType.DEBIT.value:
                extra = ""
            lines.append(f"- {card.name}: {card.type} vinculado a {account_label}{extra}")
        return "\n".join(lines)

    def invoice_message(self, card_text: str | None = None) -> str:
        if not card_text:
            total = sum((card.current_invoice for card in self._card_repository.list()), Decimal("0"))
            return f"Fatura total atual: {format_money(total)}."

        resolution = self._card_resolver.resolve(card_text)
        if resolution.is_ambiguous:
            options = ", ".join(card.name for card in resolution.matches)
            return f"Encontrei mais de um cartao. Qual deles? {options}."
        if resolution.card is None:
            return f"Nao encontrei o cartao {display_account_name(card_text)}."
        return f"Fatura atual de {resolution.card.name}: {format_money(resolution.card.current_invoice)}."

    def find_card_in_text(self, text: str) -> CardRecord | None:
        normalized = _normalize_card_text(text)
        for card in self._card_repository.list():
            card_name = _normalize_card_text(card.name)
            compact_name = card_name.replace("cartao ", "")
            if card_name in normalized or compact_name in normalized:
                return card
        return None

    def register_expense_on_card(self, card: CardRecord, amount: Decimal) -> None:
        if card.type == CardType.CREDIT.value:
            self._card_repository.adjust_invoice(card.id, amount)

    def pay_invoice_from_text(self, text: str) -> str | None:
        normalized = _normalize_card_text(text)
        if "fatura" not in normalized or not any(word in normalized for word in ("paguei", "pagar")):
            return None

        amount = _extract_money(normalized)
        card = self.find_card_in_text(normalized)
        account = self._extract_payment_account(normalized)
        if amount is None:
            return "Qual foi o valor pago da fatura?"
        if card is None:
            return "De qual cartao voce pagou a fatura?"
        if account is None:
            return "De qual conta saiu o pagamento da fatura?"

        self._card_repository.adjust_invoice(card.id, -amount)
        self._account_repository.adjust_balance(account.id, -amount)
        return (
            f"Pagamento de fatura registrado: {format_money(amount)} do cartao "
            f"{card.name}, pago pela conta {account.name}."
        )

    def _add_from_text(self, text: str) -> str:
        normalized = _normalize_card_text(text)
        card_type = _extract_card_type(normalized)
        if card_type is None:
            return "Esse cartao e de credito ou debito?"

        name = _extract_card_name(normalized)
        if not name:
            return "Qual e o nome do cartao?"

        account = self._extract_linked_account(normalized)
        if account is None:
            return f"A qual conta o cartao {name} deve ficar vinculado?"

        existing = self._card_repository.get_by_name(name)
        if existing:
            return f"O cartao {existing.name} ja esta cadastrado."

        record = self._card_repository.add(
            CardDraft(
                name=name,
                type=card_type,
                linked_account_id=account.id,
                limit=_extract_limit(normalized),
                closing_day=_extract_day(normalized, "fechamento"),
                due_day=_extract_day(normalized, "vencimento"),
            )
        )
        return f"Cartao cadastrado: {record.name} {record.type} vinculado a {account.name}."

    def _extract_linked_account(self, normalized_text: str) -> AccountRecord | None:
        patterns = (
            r"(?:conta|vinculado a|associado ao|associado a)\s+(.+?)(?:\s+com\s+limite|\s+limite|\s+fechamento|\s+vencimento|$)",
            r"ao\s+(.+?)(?:\s+com\s+limite|\s+limite|\s+fechamento|\s+vencimento|$)",
        )
        for pattern in patterns:
            match = re.search(pattern, normalized_text)
            if match:
                account = self._account_resolver.resolve(match.group(1)).account
                if account:
                    return account
        return None

    def _extract_payment_account(self, normalized_text: str) -> AccountRecord | None:
        match = re.search(r"\b(?:com|pela|pelo|da|do)\s+(.+)$", normalized_text)
        if not match:
            return None
        return self._account_resolver.resolve(match.group(1)).account

    def _linked_account(self, card: CardRecord) -> AccountRecord | None:
        if not card.linked_account_id:
            return None
        return self._account_repository.get(card.linked_account_id)

    @property
    def resolver(self) -> CardResolver:
        return self._card_resolver


def _extract_card_type(normalized_text: str) -> CardType | None:
    if "credito" in normalized_text:
        return CardType.CREDIT
    if "debito" in normalized_text:
        return CardType.DEBIT
    return None


def _extract_card_name(normalized_text: str) -> str | None:
    match = re.search(
        r"(?:criar|adicionar|cadastrar)?\s*(?:cartao\s+)?(.+?)\s+(?:credito|debito)",
        normalized_text,
    )
    if not match:
        return None
    name = display_account_name(match.group(1))
    if not name.lower().startswith("cartao"):
        name = f"Cartao {name}"
    return name


def _extract_limit(normalized_text: str) -> Decimal | None:
    match = re.search(r"\blimite\s+(?:de\s+)?(?:r\$\s*)?([\d.,]+)", normalized_text)
    return parse_decimal(match.group(1)) if match else None


def _extract_day(normalized_text: str, label: str) -> int | None:
    match = re.search(rf"\b{label}\s+dia\s+(\d{{1,2}})\b", normalized_text)
    if not match:
        return None
    day = int(match.group(1))
    return day if 1 <= day <= 31 else None


def _extract_money(normalized_text: str) -> Decimal | None:
    match = re.search(r"(?:r\$\s*)?(\d{1,3}(?:\.\d{3})+(?:,\d{2})?|\d+(?:[,.]\d{1,2})?)", normalized_text)
    return parse_decimal(match.group(1)) if match else None


def _normalize_card_text(text: str) -> str:
    from finbot.services.accounts import normalize_text

    return normalize_text(text)
