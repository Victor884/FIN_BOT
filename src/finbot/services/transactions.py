from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, ROUND_DOWN
from enum import StrEnum
from time import perf_counter
from uuid import uuid4

from finbot.db.models import TransactionRecord
from finbot.db.repositories import AccountRepository, CardRepository, TransactionRepository
from finbot.models.card import CardType
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
    CONFIRMATION_REQUIRED = "confirmation_required"


@dataclass(frozen=True)
class TransactionEntryResult:
    status: TransactionEntryStatus
    message: str
    transaction_id: str | None = None
    record: TransactionRecord | None = None
    draft: TransactionDraft | None = None
    missing_fields: tuple[str, ...] = ()
    validation: ValidationResult | None = None
    parser_duration_ms: int = 0
    validation_duration_ms: int = 0
    database_duration_ms: int = 0
    ai_duration_ms: int = 0
    parser_source: str = "rules"

    @property
    def is_recorded(self) -> bool:
        return self.status == TransactionEntryStatus.RECORDED


class TransactionEntryService:
    def __init__(
        self,
        repository: TransactionRepository,
        parser: FinancialParser | None = None,
        account_repository: AccountRepository | None = None,
        card_repository: CardRepository | None = None,
        confirmation_threshold: float = 0.75,
    ) -> None:
        self._repository = repository
        self._parser = parser or RuleBasedParser()
        self._account_repository = account_repository
        self._card_repository = card_repository
        self._account_resolver = (
            AccountResolver(account_repository) if account_repository is not None else None
        )
        self._confirmation_threshold = confirmation_threshold

    def record_from_text(self, text: str) -> TransactionEntryResult:
        parser_start = perf_counter()
        parse_result = self._parser.parse(text)
        parser_duration_ms = round((perf_counter() - parser_start) * 1000)
        timing = {
            "parser_duration_ms": parser_duration_ms,
            "ai_duration_ms": parse_result.ai_duration_ms,
            "parser_source": parse_result.source,
        }
        if parse_result.draft is None:
            return TransactionEntryResult(
                status=TransactionEntryStatus.NEEDS_MORE_INFO,
                message=_build_missing_fields_message(parse_result.missing_fields),
                missing_fields=parse_result.missing_fields,
                **timing,
            )

        draft = self._resolve_accounts(parse_result.draft)
        draft = self._resolve_card(text, draft)
        missing_transfer_message = self._build_missing_transfer_account_message(draft)
        if missing_transfer_message:
            return TransactionEntryResult(
                status=TransactionEntryStatus.NEEDS_MORE_INFO,
                message=missing_transfer_message,
                draft=draft,
                **timing,
            )

        validation_start = perf_counter()
        validation = validate_transaction(draft)
        validation_duration_ms = round((perf_counter() - validation_start) * 1000)
        timing["validation_duration_ms"] = validation_duration_ms
        if not validation.is_valid:
            return TransactionEntryResult(
                status=TransactionEntryStatus.INVALID,
                message=_build_validation_error_message(validation.errors, draft),
                draft=draft,
                validation=validation,
                **timing,
            )

        if parse_result.needs_confirmation or draft.confidence < self._confirmation_threshold:
            return TransactionEntryResult(
                status=TransactionEntryStatus.CONFIRMATION_REQUIRED,
                message=_build_confirmation_message(draft),
                draft=draft,
                validation=validation,
                **timing,
            )

        return self.record_draft(draft, validation=validation, timing=timing)

    def record_draft(
        self,
        draft: TransactionDraft,
        *,
        validation: ValidationResult | None = None,
        timing: dict[str, object] | None = None,
    ) -> TransactionEntryResult:
        timing = dict(timing or {})
        if validation is None:
            validation_start = perf_counter()
            validation = validate_transaction(draft)
            timing["validation_duration_ms"] = round((perf_counter() - validation_start) * 1000)
        if not validation.is_valid:
            return TransactionEntryResult(
                status=TransactionEntryStatus.INVALID,
                message=_build_validation_error_message(validation.errors, draft),
                draft=draft,
                validation=validation,
                **timing,
            )

        database_start = perf_counter()
        dedupe_key = build_transaction_dedupe_key(draft)
        existing_record = self._repository.get_by_dedupe_key(dedupe_key)
        database_duration_ms = round((perf_counter() - database_start) * 1000)
        timing["database_duration_ms"] = int(timing.get("database_duration_ms", 0)) + database_duration_ms
        if existing_record is not None:
            return TransactionEntryResult(
                status=TransactionEntryStatus.DUPLICATE,
                message=_build_duplicate_message(existing_record),
                transaction_id=existing_record.id,
                record=existing_record,
                draft=draft,
                validation=validation,
                **timing,
            )

        database_start = perf_counter()
        records = self._create_records(draft)
        for record in records:
            self._apply_account_balance_changes(record)
        record = records[0]
        timing["database_duration_ms"] = int(timing.get("database_duration_ms", 0)) + round(
            (perf_counter() - database_start) * 1000
        )
        return TransactionEntryResult(
            status=TransactionEntryStatus.RECORDED,
            message=_build_success_message(record, len(records)),
            transaction_id=record.id,
            record=record,
            draft=draft,
            validation=validation,
            **timing,
        )

    def update_from_text(
        self, record: TransactionRecord, text: str
    ) -> TransactionEntryResult:
        parsed = self._parser.parse(text)
        if parsed.draft is None:
            return TransactionEntryResult(
                status=TransactionEntryStatus.NEEDS_MORE_INFO,
                message=_build_missing_fields_message(parsed.missing_fields),
                missing_fields=parsed.missing_fields,
            )
        draft = self._resolve_card(text, self._resolve_accounts(parsed.draft))
        validation = validate_transaction(draft)
        if not validation.is_valid:
            return TransactionEntryResult(
                status=TransactionEntryStatus.INVALID,
                message=_build_validation_error_message(validation.errors, draft),
                draft=draft,
                validation=validation,
            )
        duplicate = self._repository.get_by_dedupe_key(build_transaction_dedupe_key(draft))
        if duplicate is not None and duplicate.id != record.id:
            return TransactionEntryResult(
                status=TransactionEntryStatus.DUPLICATE,
                message=_build_duplicate_message(duplicate),
                record=duplicate,
                transaction_id=duplicate.id,
                draft=draft,
                validation=validation,
            )
        self._reverse_account_balance_changes(record)
        self._repository.update_from_draft(record, draft, build_transaction_dedupe_key(draft))
        self._apply_account_balance_changes(record)
        return TransactionEntryResult(
            status=TransactionEntryStatus.RECORDED,
            message=f"Lancamento atualizado: {_build_success_message(record)}",
            record=record,
            transaction_id=record.id,
            draft=draft,
            validation=validation,
        )

    def delete_record(self, record: TransactionRecord) -> None:
        self._reverse_account_balance_changes(record)
        self._repository.delete(record)

    def apply_due_transactions(self, today: date | None = None) -> int:
        applied = 0
        for record in self._repository.list_unapplied_due(today or date.today()):
            self._apply_account_balance_changes(record)
            applied += 1
        return applied

    def _create_records(self, draft: TransactionDraft) -> list[TransactionRecord]:
        installments = draft.installment_total or 1
        if installments == 1:
            return [self._repository.add(draft, dedupe_key=build_transaction_dedupe_key(draft))]

        group_id = str(uuid4())
        amounts = _split_amount(draft.amount, installments)
        records: list[TransactionRecord] = []
        for number, amount in enumerate(amounts, start=1):
            installment_draft = replace(
                draft,
                amount=amount,
                transaction_date=_add_months(draft.transaction_date, number - 1),
                description=f"{draft.description} ({number}/{installments})",
                is_recurring=False,
                installment_total=installments,
            )
            records.append(
                self._repository.add_installment(
                    installment_draft,
                    dedupe_key=build_transaction_dedupe_key(installment_draft),
                    group_id=group_id,
                    number=number,
                    total=installments,
                )
            )
        return records

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
        if self._account_repository is None or record.balance_applied:
            return
        if record.transaction_date > date.today():
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

        if (
            self._card_repository is not None
            and record.type == TransactionType.EXPENSE.value
            and record.card_name
        ):
            card = self._card_repository.get_by_name(record.card_name)
            if card and card.type == CardType.CREDIT.value:
                self._card_repository.adjust_invoice(card.id, record.amount)
        record.balance_applied = True

    def _reverse_account_balance_changes(self, record: TransactionRecord) -> None:
        if self._account_repository is None or not record.balance_applied:
            return

        if record.type == TransactionType.EXPENSE.value and record.account_from:
            account = self._account_resolver.resolve(record.account_from).account
            if account:
                self._account_repository.adjust_balance(account.id, record.amount)
        elif record.type == TransactionType.INCOME.value:
            account_name = record.account_to or record.account_from
            account = self._account_resolver.resolve(account_name).account if account_name else None
            if account:
                self._account_repository.adjust_balance(account.id, -record.amount)
        elif record.type == TransactionType.TRANSFER.value:
            origin = self._account_resolver.resolve(record.account_from).account if record.account_from else None
            destination = (
                self._account_resolver.resolve(record.account_to).account if record.account_to else None
            )
            if origin:
                self._account_repository.adjust_balance(origin.id, record.amount)
            if destination:
                self._account_repository.adjust_balance(destination.id, -record.amount)

        if self._card_repository is not None and record.type == TransactionType.EXPENSE.value and record.card_name:
            card = self._card_repository.get_by_name(record.card_name)
            if card and card.type == CardType.CREDIT.value:
                self._card_repository.adjust_invoice(card.id, -record.amount)
        record.balance_applied = False

    def _resolve_card(self, text: str, draft: TransactionDraft) -> TransactionDraft:
        if self._card_repository is None or draft.type != TransactionType.EXPENSE:
            return draft

        normalized_text = text.lower()
        for card in self._card_repository.list():
            normalized_card = card.name.lower().replace("cartao ", "").strip()
            if card.name.lower() not in normalized_text and normalized_card not in normalized_text:
                continue

            if card.type == CardType.CREDIT.value:
                return replace(
                    draft,
                    card_name=card.name,
                    payment_method="cartao_credito",
                    account_from=None,
                )

            account_name = draft.account_from
            if self._account_repository and card.linked_account_id:
                account = self._account_repository.get(card.linked_account_id)
                account_name = account.name if account else account_name
            return replace(
                draft,
                card_name=card.name,
                payment_method="cartao_debito",
                account_from=account_name,
            )

        return draft


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


def _build_success_message(record: TransactionRecord, installment_count: int = 1) -> str:
    amount = format_money(record.amount)
    category = f" - Categoria: {record.category}" if record.category else ""
    installment = ""
    if installment_count > 1:
        installment = f" Foram criadas {installment_count} parcelas mensais."
    if record.type == TransactionType.TRANSFER.value:
        return f"Transferencia registrada: {amount} de {record.account_from} para {record.account_to}."
    type_label = "Receita" if record.type == TransactionType.INCOME.value else "Despesa"
    return f"Lancamento registrado: {type_label} de {amount} - {record.description}{category}.{installment}"


def _build_duplicate_message(record: TransactionRecord) -> str:
    amount = format_money(record.amount)
    return f"Este lancamento parece duplicado: {amount} em {record.description}."


def _build_confirmation_message(draft: TransactionDraft) -> str:
    type_label = {
        TransactionType.EXPENSE: "Despesa",
        TransactionType.INCOME: "Receita",
        TransactionType.TRANSFER: "Transferencia",
    }.get(draft.type, "Movimentacao")
    category = f"\nCategoria: {draft.category}" if draft.category else ""
    installments = f"\nParcelas: {draft.installment_total}x" if draft.installment_total else ""
    return (
        "Preciso confirmar este lancamento antes de salvar:\n"
        f"{type_label}: {format_money(draft.amount)} - {draft.description}{category}{installments}\n"
        "Responda SIM para confirmar ou NAO para descartar."
    )


def _split_amount(total: Decimal, installments: int) -> list[Decimal]:
    cents = (total * 100).quantize(Decimal("1"), rounding=ROUND_DOWN)
    base_cents, remainder = divmod(int(cents), installments)
    return [Decimal(base_cents + (1 if index < remainder else 0)) / 100 for index in range(installments)]


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    import calendar

    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))
