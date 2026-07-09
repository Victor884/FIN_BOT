from dataclasses import dataclass, replace
from enum import StrEnum

from finbot.db.models import TransactionRecord
from finbot.db.repositories import AccountRepository, TransactionRepository
from finbot.models.transaction import TransactionDraft, TransactionType
from finbot.parser.contracts import FinancialParser
from finbot.parser.rules import RuleBasedParser
from finbot.services.accounts import AccountResolver, format_money
from finbot.services.deduplication import build_transaction_dedupe_key
from finbot.validation.transaction import ValidationResult, validate_transaction


class TransactionEntryStatus(StrEnum):
    RECORDED = "recorded"
    NEEDS_MORE_INFO = "needs_more_info"
    INVALID = "invalid"
    DUPLICATE = "duplicate"


@dataclass(frozen=True)
class TransactionEntryResult:
    status: TransactionEntryStatus
    message: str
    transaction_id: str | None = None
    record: TransactionRecord | None = None
    draft: TransactionDraft | None = None
    missing_fields: tuple[str, ...] = ()
    validation: ValidationResult | None = None

    @property
    def is_recorded(self) -> bool:
        return self.status == TransactionEntryStatus.RECORDED


class TransactionEntryService:
    def __init__(
        self,
        repository: TransactionRepository,
        parser: FinancialParser | None = None,
        account_repository: AccountRepository | None = None,
    ) -> None:
        self._repository = repository
        self._parser = parser or RuleBasedParser()
        self._account_repository = account_repository
        self._account_resolver = (
            AccountResolver(account_repository) if account_repository is not None else None
        )

    def record_from_text(self, text: str) -> TransactionEntryResult:
        parse_result = self._parser.parse(text)
        if parse_result.draft is None:
            return TransactionEntryResult(
                status=TransactionEntryStatus.NEEDS_MORE_INFO,
                message=_build_missing_fields_message(parse_result.missing_fields),
                missing_fields=parse_result.missing_fields,
            )

        draft = self._resolve_accounts(parse_result.draft)
        missing_transfer_message = self._build_missing_transfer_account_message(draft)
        if missing_transfer_message:
            return TransactionEntryResult(
                status=TransactionEntryStatus.NEEDS_MORE_INFO,
                message=missing_transfer_message,
                draft=draft,
            )

        validation = validate_transaction(draft)
        if not validation.is_valid:
            return TransactionEntryResult(
                status=TransactionEntryStatus.INVALID,
                message=_build_validation_error_message(validation.errors, draft),
                draft=draft,
                validation=validation,
            )

        dedupe_key = build_transaction_dedupe_key(draft)
        existing_record = self._repository.get_by_dedupe_key(dedupe_key)
        if existing_record is not None:
            return TransactionEntryResult(
                status=TransactionEntryStatus.DUPLICATE,
                message=_build_duplicate_message(existing_record),
                transaction_id=existing_record.id,
                record=existing_record,
                draft=draft,
                validation=validation,
            )

        record = self._repository.add(draft, dedupe_key=dedupe_key)
        self._apply_account_balance_changes(record)
        return TransactionEntryResult(
            status=TransactionEntryStatus.RECORDED,
            message=_build_success_message(record),
            transaction_id=record.id,
            record=record,
            draft=draft,
            validation=validation,
        )

    def _resolve_accounts(self, draft: TransactionDraft) -> TransactionDraft:
        if self._account_resolver is None:
            return draft

        account_from = draft.account_from
        account_to = draft.account_to

        if account_from:
            resolution = self._account_resolver.resolve(account_from)
            if resolution.is_ambiguous:
                return draft
            account_from = resolution.canonical_name or account_from

        if account_to:
            resolution = self._account_resolver.resolve(account_to)
            if resolution.is_ambiguous:
                names = ", ".join(account.name for account in resolution.matches)
                return replace(draft, account_to=f"AMBIGUOUS:{names}")
            account_to = resolution.canonical_name or account_to

        return replace(draft, account_from=account_from, account_to=account_to)

    def _build_missing_transfer_account_message(self, draft: TransactionDraft) -> str | None:
        if draft.type != TransactionType.TRANSFER:
            return None
        amount = format_money(draft.amount)
        if draft.account_to and draft.account_to.startswith("AMBIGUOUS:"):
            options = draft.account_to.removeprefix("AMBIGUOUS:")
            return f"Voce quer registrar essa transferencia para qual conta? {options} ou outra?"
        if not draft.account_from and draft.account_to:
            return (
                f"Entendi que e uma transferencia de {amount} para {draft.account_to}. "
                "De qual conta saiu esse valor?"
            )
        if draft.account_from and not draft.account_to:
            return (
                f"Entendi que e uma transferencia de {amount} saindo de {draft.account_from}. "
                "Para qual conta foi esse valor?"
            )
        return None

    def _apply_account_balance_changes(self, record: TransactionRecord) -> None:
        if self._account_repository is None:
            return

        if record.type == TransactionType.EXPENSE.value and record.account_from:
            account = self._account_resolver.resolve(record.account_from).account
            if account:
                self._account_repository.adjust_balance(account.id, -record.amount)
        elif record.type == TransactionType.INCOME.value:
            account_name = record.account_to or record.account_from
            account = self._account_resolver.resolve(account_name).account if account_name else None
            if account:
                self._account_repository.adjust_balance(account.id, record.amount)
        elif record.type == TransactionType.TRANSFER.value:
            origin = self._account_resolver.resolve(record.account_from).account if record.account_from else None
            destination = (
                self._account_resolver.resolve(record.account_to).account if record.account_to else None
            )
            if origin:
                self._account_repository.adjust_balance(origin.id, -record.amount)
            if destination:
                self._account_repository.adjust_balance(destination.id, record.amount)


def _build_missing_fields_message(missing_fields: tuple[str, ...]) -> str:
    if "amount" in missing_fields and "type" not in missing_fields:
        return "Entendi a movimentacao, mas faltou o valor. Qual foi o valor?"
    return (
        "Nao consegui entender essa mensagem como uma movimentacao financeira. "
        "Envie algo como: 'Gastei R$ 45 no mercado hoje' ou use /ajuda para ver exemplos."
    )


def _build_validation_error_message(errors: tuple[str, ...], draft: TransactionDraft) -> str:
    if "description_required" in errors and draft.type == TransactionType.EXPENSE:
        return f"Voce gastou {format_money(draft.amount)} com o que?"
    if "amount_must_be_positive" in errors:
        return "O valor precisa ser maior que zero."
    return (
        "Nao consegui registrar essa movimentacao com seguranca. "
        "Pode enviar novamente com valor, descricao e conta?"
    )


def _build_success_message(record: TransactionRecord) -> str:
    amount = format_money(record.amount)
    category = f" - Categoria: {record.category}" if record.category else ""
    if record.type == TransactionType.TRANSFER.value:
        return f"Transferencia registrada: {amount} de {record.account_from} para {record.account_to}."
    type_label = "Receita" if record.type == TransactionType.INCOME.value else "Despesa"
    return f"Lancamento registrado: {type_label} de {amount} - {record.description}{category}."


def _build_duplicate_message(record: TransactionRecord) -> str:
    amount = format_money(record.amount)
    return f"Este lancamento parece duplicado: {amount} em {record.description}."
