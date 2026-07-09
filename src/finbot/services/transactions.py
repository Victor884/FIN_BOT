from dataclasses import dataclass
from enum import StrEnum

from finbot.db.models import TransactionRecord
from finbot.db.repositories import TransactionRepository
from finbot.models.transaction import TransactionDraft
from finbot.parser.contracts import FinancialParser
from finbot.parser.rules import RuleBasedParser
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
    ) -> None:
        self._repository = repository
        self._parser = parser or RuleBasedParser()

    def record_from_text(self, text: str) -> TransactionEntryResult:
        parse_result = self._parser.parse(text)
        if parse_result.draft is None:
            return TransactionEntryResult(
                status=TransactionEntryStatus.NEEDS_MORE_INFO,
                message=_build_missing_fields_message(parse_result.missing_fields),
                missing_fields=parse_result.missing_fields,
            )

        validation = validate_transaction(parse_result.draft)
        if not validation.is_valid:
            return TransactionEntryResult(
                status=TransactionEntryStatus.INVALID,
                message=_build_validation_error_message(validation.errors),
                draft=parse_result.draft,
                validation=validation,
            )

        dedupe_key = build_transaction_dedupe_key(parse_result.draft)
        existing_record = self._repository.get_by_dedupe_key(dedupe_key)
        if existing_record is not None:
            return TransactionEntryResult(
                status=TransactionEntryStatus.DUPLICATE,
                message=_build_duplicate_message(existing_record),
                transaction_id=existing_record.id,
                draft=parse_result.draft,
                validation=validation,
            )

        record = self._repository.add(parse_result.draft, dedupe_key=dedupe_key)
        return TransactionEntryResult(
            status=TransactionEntryStatus.RECORDED,
            message=_build_success_message(record),
            transaction_id=record.id,
            draft=parse_result.draft,
            validation=validation,
        )


def _build_missing_fields_message(missing_fields: tuple[str, ...]) -> str:
    if not missing_fields:
        return "Nao consegui interpretar a movimentacao. Pode enviar mais detalhes?"

    fields = ", ".join(missing_fields)
    return f"Faltam dados para registrar a movimentacao: {fields}."


def _build_validation_error_message(errors: tuple[str, ...]) -> str:
    fields = ", ".join(errors)
    return f"Nao foi possivel registrar a movimentacao: {fields}."


def _build_success_message(record: TransactionRecord) -> str:
    amount = f"R$ {record.amount:.2f}".replace(".", ",")
    return f"Lancamento registrado: {amount} em {record.description}."


def _build_duplicate_message(record: TransactionRecord) -> str:
    amount = f"R$ {record.amount:.2f}".replace(".", ",")
    return f"Este lancamento parece duplicado: {amount} em {record.description}."
