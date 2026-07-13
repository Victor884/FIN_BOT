import logging
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from finbot.db.models import TransactionRecord
from finbot.db.repositories import (
    AccountRepository,
    CardRepository,
    CategoryRepository,
    ConversationRepository,
    RecurringTransactionRepository,
    TransactionRepository,
)
from finbot.models.transaction import TransactionDraft, TransactionStatus, TransactionType
from finbot.services.accounts import AccountService, format_money
from finbot.services.categories import CategoryService
from finbot.services.cards import CardService
from finbot.services.recurrences import RecurringTransactionService
from finbot.services.transactions import TransactionEntryResult, TransactionEntryService
from finbot.services.web_link import WebLinkService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BotMessageResult:
    status: str
    message: str
    records: tuple[TransactionRecord, ...] = ()
    entry_results: tuple[TransactionEntryResult, ...] = ()


class BotMessageService:
    def __init__(
        self,
        transaction_service: TransactionEntryService,
        transaction_repository: TransactionRepository,
        account_repository: AccountRepository,
        card_repository: CardRepository | None = None,
        category_repository: CategoryRepository | None = None,
        conversation_repository: ConversationRepository | None = None,
        recurring_repository: RecurringTransactionRepository | None = None,
    ) -> None:
        self._transaction_service = transaction_service
        self._transaction_repository = transaction_repository
        self._account_repository = account_repository
        self._card_repository = card_repository
        self._category_repository = category_repository
        self._conversation_repository = conversation_repository
        self._recurring_repository = recurring_repository
        self._account_service = AccountService(account_repository)
        self._card_service = CardService(card_repository, account_repository) if card_repository else None
        self._category_service = CategoryService(category_repository) if category_repository else None
        self._recurring_service = (
            RecurringTransactionService(recurring_repository, transaction_service)
            if recurring_repository
            else None
        )

    def bind_user(self, user_id: str) -> None:
        """Scope all repositories in this request to the authenticated Telegram user."""
        self._transaction_repository.user_id = user_id
        self._account_repository.user_id = user_id
        if self._card_repository is not None:
            self._card_repository.user_id = user_id
        if self._category_repository is not None:
            self._category_repository.user_id = user_id
        if self._conversation_repository is not None:
            self._conversation_repository.user_id = user_id
        if self._recurring_repository is not None:
            self._recurring_repository.user_id = user_id

    @property
    def session(self):  # type: ignore[no-untyped-def]
        return self._transaction_repository._session

    @property
    def user_id(self) -> str | None:
        return self._transaction_repository.user_id

    def handle_text(self, text: str) -> BotMessageResult:
        stripped = text.strip()
        if stripped.startswith("/"):
            return self._handle_command(stripped)

        conversation_result = self._handle_conversation(stripped)
        if conversation_result is not None:
            return conversation_result

        account_message = self._account_service.try_add_from_natural_text(stripped)
        if account_message is not None:
            return BotMessageResult(status="account_added", message=account_message)

        if self._card_service is not None:
            invoice_payment_message = self._card_service.pay_invoice_from_text(stripped)
            if invoice_payment_message is not None:
                return BotMessageResult(status="invoice_paid", message=invoice_payment_message)

            card_message = self._card_service.try_add_from_natural_text(stripped)
            if card_message is not None:
                return BotMessageResult(status="card_added", message=card_message)

        items = split_financial_entries(stripped)
        logger.info("telegram_message_split count=%s is_multiple=%s", len(items), len(items) > 1)
        results = tuple(self._transaction_service.record_from_text(item) for item in items)
        for result in results:
            if result.status.value == "confirmation_required" and result.draft is not None:
                self._save_confirmation(result.draft)
            if result.is_recorded and result.record is not None:
                self._after_recorded(result.record)
        records = tuple(result.record for result in results if result.is_recorded and result.record)

        if len(results) == 1:
            return BotMessageResult(
                status=results[0].status.value,
                message=results[0].message,
                records=records,
                entry_results=results,
            )

        return BotMessageResult(
            status="batch_processed",
            message=build_batch_message(results),
            records=records,
            entry_results=results,
        )

    def _handle_command(self, text: str) -> BotMessageResult:
        command, _, args = text.partition(" ")
        command = command.lower()
        args = args.strip()

        if command == "/vincular":
            if self._transaction_repository.user_id is None:
                return BotMessageResult(
                    status="link_unavailable",
                    message="Nao consegui identificar sua conta do Telegram agora.",
                )
            code = WebLinkService(self.session).create_code(self._transaction_repository.user_id)
            return BotMessageResult(
                status="link_code",
                message=(
                    "Use este codigo no acesso web do FIN_BOT: "
                    f"{code}\nEle expira em 10 minutos e so pode ser usado uma vez."
                ),
            )

        if command == "/contas":
            return BotMessageResult(status="accounts", message=self._account_service.list_accounts())
        if command == "/addconta":
            return BotMessageResult(status="account_added", message=self._account_service.add_from_command(text))
        if command == "/saldo":
            return BotMessageResult(status="balance", message=self._account_service.balance_message(args or None))
        if command == "/cartoes":
            return BotMessageResult(status="cards", message=self._cards_message())
        if command == "/addcartao":
            return BotMessageResult(status="card_added", message=self._add_card_message(text))
        if command == "/fatura":
            return BotMessageResult(status="invoice", message=self._invoice_message(args or None))
        if command == "/relatorio":
            return BotMessageResult(status="account_report", message=self._account_report(args))
        if command == "/relatoriogeral":
            return BotMessageResult(status="general_report", message=self._general_report())
        if command == "/categorias":
            return BotMessageResult(
                status="categories",
                message=self._category_service.list_message() if self._category_service else categories_message(),
            )
        if command == "/categoria":
            return BotMessageResult(status="category", message=self._category_command(args))
        if command == "/ultimos":
            return BotMessageResult(status="recent", message=self._recent_transactions(args))
        if command == "/resumo":
            return BotMessageResult(status="summary", message=self._quick_month_summary())
        if command == "/pendentes":
            return BotMessageResult(status="pending", message=self._pending_transactions())
        if command == "/exportar":
            return BotMessageResult(status="export", message=export_message())
        if command == "/cancelar":
            if self._conversation_repository is not None:
                self._conversation_repository.clear()
            return BotMessageResult(status="cancelled", message="Operacao pendente cancelada.")
        if command == "/editar":
            return self._start_selection("edit")
        if command == "/excluir":
            return self._start_selection("delete")
        if command in {"/ajuda", "/start"}:
            return BotMessageResult(status="help", message=help_message())

        return BotMessageResult(status="unknown_command", message="Comando nao reconhecido. Use /ajuda.")

    def _cards_message(self) -> str:
        if self._card_service is None:
            return "Modulo de cartoes indisponivel."
        return self._card_service.list_cards()

    def _add_card_message(self, text: str) -> str:
        if self._card_service is None:
            return "Modulo de cartoes indisponivel."
        return self._card_service.add_from_command(text)

    def _invoice_message(self, card_text: str | None) -> str:
        if self._card_service is None:
            return "Modulo de cartoes indisponivel."
        return self._card_service.invoice_message(card_text)

    def _account_report(self, account_text: str) -> str:
        if not account_text:
            return "Informe a conta. Exemplo: /relatorio Inter"

        resolution = self._account_service.resolver.resolve(account_text)
        if resolution.is_ambiguous:
            options = ", ".join(account.name for account in resolution.matches)
            return f"Encontrei mais de uma conta. Qual delas? {options}."
        if resolution.account is None:
            return f"Nao encontrei a conta {account_text}."

        account = resolution.account
        records = self._transaction_repository.list_by_account(account.name, limit=200)
        income = sum(
            (record.amount for record in records if record.type == TransactionType.INCOME.value),
            Decimal("0"),
        )
        expenses = sum(
            (record.amount for record in records if record.type == TransactionType.EXPENSE.value),
            Decimal("0"),
        )
        transfer_in = sum(
            (
                record.amount
                for record in records
                if record.type == TransactionType.TRANSFER.value and record.account_to == account.name
            ),
            Decimal("0"),
        )
        transfer_out = sum(
            (
                record.amount
                for record in records
                if record.type == TransactionType.TRANSFER.value and record.account_from == account.name
            ),
            Decimal("0"),
        )

        lines = [
            f"Relatorio de {account.name}",
            f"Saldo atual: {format_money(account.current_balance)}",
            f"Receitas: {format_money(income)}",
            f"Despesas: {format_money(expenses)}",
            f"Transferencias de entrada: {format_money(transfer_in)}",
            f"Transferencias de saida: {format_money(transfer_out)}",
            "",
            "Gastos por categoria:",
            *format_category_totals(records),
            "",
            "Ultimas movimentacoes:",
            *format_recent_records(records[:5]),
        ]
        return "\n".join(lines)

    def _general_report(self) -> str:
        today = date.today()
        start = date(today.year, today.month, 1)
        records = self._transaction_repository.list_between(start, today)
        accounts = self._account_repository.list()
        total_balance = sum((account.current_balance for account in accounts), Decimal("0"))
        income = sum(
            (record.amount for record in records if record.type == TransactionType.INCOME.value),
            Decimal("0"),
        )
        expenses = sum(
            (record.amount for record in records if record.type == TransactionType.EXPENSE.value),
            Decimal("0"),
        )

        lines = [
            "Relatorio geral",
            f"Saldo total: {format_money(total_balance)}",
            f"Receitas do mes: {format_money(income)}",
            f"Despesas do mes: {format_money(expenses)}",
            f"Saldo mensal: {format_money(income - expenses)}",
            "",
            "Gastos por categoria:",
            *format_category_totals(records),
            "",
            "Ultimas movimentacoes:",
            *format_recent_records(self._transaction_repository.list(limit=5)),
        ]
        return "\n".join(lines)

    def _recent_transactions(self, args: str) -> str:
        limit = 5
        if args.strip().isdigit():
            limit = max(1, min(20, int(args.strip())))
        records = self._transaction_repository.list(limit=limit)
        lines = [f"Ultimos {len(records)} lancamentos:"]
        lines.extend(format_recent_records(records))
        return "\n".join(lines)

    def _quick_month_summary(self) -> str:
        today = date.today()
        start = date(today.year, today.month, 1)
        records = self._transaction_repository.list_between(start, today)
        income = sum(
            (record.amount for record in records if record.type == TransactionType.INCOME.value),
            Decimal("0"),
        )
        expenses = sum(
            (record.amount for record in records if record.type == TransactionType.EXPENSE.value),
            Decimal("0"),
        )
        days_elapsed = max(1, (today - start).days + 1)
        daily_average = expenses / Decimal(days_elapsed)
        return "\n".join(
            [
                "Resumo do mes:",
                f"Receitas: {format_money(income)}",
                f"Despesas: {format_money(expenses)}",
                f"Saldo: {format_money(income - expenses)}",
                f"Media diaria de gastos: {format_money(daily_average)}",
            ]
        )

    def _pending_transactions(self) -> str:
        records = self._transaction_repository.list_pending()
        if not records:
            return "Nenhuma despesa pendente encontrada."
        lines = ["Despesas pendentes:"]
        lines.extend(format_recent_records(records))
        return "\n".join(lines)

    def _category_command(self, args: str) -> str:
        if self._category_service is None:
            return "Categorias personalizadas indisponiveis."
        action, _, name = args.partition(" ")
        if action.lower() in {"adicionar", "add"}:
            return self._category_service.add(name)
        if action.lower() in {"remover", "excluir", "delete"}:
            return self._category_service.delete(name)
        return "Use /categoria adicionar nome ou /categoria remover nome."

    def _start_selection(self, action: str) -> BotMessageResult:
        if self._conversation_repository is None:
            return BotMessageResult(status="unavailable", message="Operacao interativa indisponivel.")
        records = self._transaction_repository.list(limit=10)
        if not records:
            return BotMessageResult(status=f"{action}_empty", message="Nao ha lancamentos para selecionar.")
        self._conversation_repository.set(
            f"select_{action}",
            {"transaction_ids": [record.id for record in records]},
            _conversation_expiry(),
        )
        verb = "editar" if action == "edit" else "excluir"
        return BotMessageResult(
            status=f"select_{action}",
            message=(f"Qual lancamento voce quer {verb}? Responda com o numero:\n" + _numbered_records(records)),
        )

    def _handle_conversation(self, text: str) -> BotMessageResult | None:
        if self._conversation_repository is None:
            return None
        conversation = self._conversation_repository.get()
        if conversation is None:
            return None
        payload = self._conversation_repository.payload(conversation)
        normalized = text.strip().lower()

        if conversation.action == "confirm_transaction":
            self._conversation_repository.clear()
            if normalized not in {"sim", "s", "confirmar"}:
                return BotMessageResult(status="confirmation_cancelled", message="Lancamento descartado.")
            draft = _draft_from_payload(payload)
            result = self._transaction_service.record_draft(draft)
            if result.is_recorded and result.record is not None:
                self._after_recorded(result.record)
            return BotMessageResult(
                status=result.status.value,
                message=result.message,
                records=(result.record,) if result.record else (),
                entry_results=(result,),
            )

        if conversation.action in {"select_edit", "select_delete"}:
            selected = _selected_record(self._transaction_repository, payload, normalized)
            if selected is None:
                return BotMessageResult(status="selection_invalid", message="Responda com um dos numeros listados ou use /cancelar.")
            if conversation.action == "select_edit":
                self._conversation_repository.set(
                    "edit_transaction", {"transaction_id": selected.id}, _conversation_expiry()
                )
                return BotMessageResult(
                    status="edit_waiting_text",
                    message=(
                        f"Lancamento selecionado: {_record_label(selected)}.\n"
                        "Envie a versao completa corrigida, por exemplo: Gastei R$ 55 em Uber categoria transporte."
                    ),
                )
            self._conversation_repository.set(
                "confirm_delete", {"transaction_id": selected.id}, _conversation_expiry()
            )
            return BotMessageResult(
                status="delete_confirmation",
                message=f"Excluir {_record_label(selected)}? Responda SIM para confirmar ou NAO para cancelar.",
            )

        transaction_id = str(payload.get("transaction_id", ""))
        record = self._transaction_repository.get(transaction_id)
        if record is None:
            self._conversation_repository.clear()
            return BotMessageResult(status="transaction_missing", message="Esse lancamento nao existe mais.")
        if conversation.action == "edit_transaction":
            result = self._transaction_service.update_from_text(record, text)
            if result.is_recorded:
                self._conversation_repository.clear()
                self._after_recorded(record, schedule_recurring=False)
            return BotMessageResult(
                status=result.status.value,
                message=result.message,
                records=(result.record,) if result.record else (),
                entry_results=(result,),
            )
        if conversation.action == "confirm_delete":
            self._conversation_repository.clear()
            if normalized not in {"sim", "s", "confirmar"}:
                return BotMessageResult(status="delete_cancelled", message="Exclusao cancelada.")
            label = _record_label(record)
            self._transaction_service.delete_record(record)
            return BotMessageResult(status="deleted", message=f"Lancamento excluido: {label}.")
        return None

    def _save_confirmation(self, draft: TransactionDraft) -> None:
        if self._conversation_repository is not None:
            self._conversation_repository.set(
                "confirm_transaction", _draft_to_payload(draft), _conversation_expiry()
            )

    def _after_recorded(self, record: TransactionRecord, *, schedule_recurring: bool = True) -> None:
        if self._category_service is not None:
            record.category = self._category_service.ensure(record.category)
        if self._recurring_service is not None and record.is_recurring and schedule_recurring:
            self._recurring_service.schedule_from_record(record)


def split_financial_entries(text: str) -> tuple[str, ...]:
    normalized = text.strip()
    if not normalized:
        return ()

    if "\n" in normalized:
        parts = normalized.splitlines()
    elif "|" in normalized:
        parts = normalized.split("|")
    elif ";" in normalized:
        parts = normalized.split(";")
    else:
        parts = [normalized]

    cleaned = []
    for part in parts:
        item = re.sub(r"^\s*(?:\d+[\).]\s*|[-*]\s*)", "", part.strip())
        if item:
            cleaned.append(item)
    return tuple(cleaned)


def build_batch_message(results: tuple[TransactionEntryResult, ...]) -> str:
    recorded = [result for result in results if result.is_recorded]
    if recorded:
        lines = [f"Registrei {len(recorded)} lancamentos:"]
    else:
        lines = ["Nao registrei nenhum lancamento:"]

    for index, result in enumerate(results, start=1):
        record = result.record
        if record is None:
            lines.append(f"{index}. {result.message}")
            continue
        type_label = {
            TransactionType.EXPENSE.value: "Despesa",
            TransactionType.INCOME.value: "Receita",
            TransactionType.TRANSFER.value: "Transferencia",
        }.get(record.type, "Movimentacao")
        category = f" - Categoria: {record.category}" if record.category else ""
        if record.type == TransactionType.TRANSFER.value:
            lines.append(
                f"{index}. {type_label}: {format_money(record.amount)} - "
                f"{record.account_from} para {record.account_to}"
            )
        else:
            lines.append(
                f"{index}. {type_label}: {format_money(record.amount)} - "
                f"{record.description}{category}"
            )
    return "\n".join(lines)


def format_category_totals(records: list[TransactionRecord]) -> list[str]:
    totals: dict[str, Decimal] = {}
    for record in records:
        if record.type != TransactionType.EXPENSE.value:
            continue
        category = record.category or "sem_categoria"
        totals[category] = totals.get(category, Decimal("0")) + record.amount
    if not totals:
        return ["- Nenhum gasto no periodo."]
    return [f"- {category}: {format_money(total)}" for category, total in sorted(totals.items())]


def format_recent_records(records: list[TransactionRecord]) -> list[str]:
    if not records:
        return ["- Nenhuma movimentacao encontrada."]
    return [
        f"- {record.transaction_date:%d/%m}: {record.description} - {format_money(record.amount)}"
        for record in records
    ]


def categories_message() -> str:
    return (
        "Categorias disponiveis:\n"
        "- Alimentacao\n- Transporte\n- Moradia\n- Saude\n- Educacao\n"
        "- Lazer\n- Vestuario\n- Receita fixa\n- Renda extra\n- Investimentos"
    )


def help_message() -> str:
    return (
        "Exemplos:\n"
        "- Gastei R$ 45 no mercado hoje\n"
        "- Recebi R$ 2.500 de salario\n"
        "- Transferi R$ 60 do banco Inter para a carteira do Mercado Pago\n"
        "- /addconta Inter saldo 2000\n"
        "- /contas\n"
        "- /saldo Inter\n"
        "- /addcartao Nubank credito conta Nubank limite 2000\n"
        "- /cartoes\n"
        "- /fatura Nubank\n"
        "- /relatorio Nubank\n"
        "- /relatoriogeral\n"
        "- /ultimos 10\n"
        "- /resumo\n"
        "- /pendentes\n"
        "- /exportar\n"
        "- /vincular (gera acesso para o dashboard web)"
    )


def export_message() -> str:
    return (
        "Vou gerar seu arquivo CSV com todos os lancamentos."
    )


def _conversation_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(minutes=10)


def _draft_to_payload(draft: TransactionDraft) -> dict[str, object]:
    return {
        "type": draft.type.value,
        "amount": str(draft.amount),
        "transaction_date": draft.transaction_date.isoformat(),
        "description": draft.description,
        "category": draft.category,
        "payment_method": draft.payment_method,
        "account_from": draft.account_from,
        "account_to": draft.account_to,
        "card_name": draft.card_name,
        "is_recurring": draft.is_recurring,
        "installment_total": draft.installment_total,
        "status": draft.status.value,
        "confidence": draft.confidence,
    }


def _draft_from_payload(payload: dict[str, object]) -> TransactionDraft:
    return TransactionDraft(
        type=TransactionType(str(payload["type"])),
        amount=Decimal(str(payload["amount"])),
        transaction_date=date.fromisoformat(str(payload["transaction_date"])),
        description=str(payload["description"]),
        category=_optional_text(payload.get("category")),
        payment_method=_optional_text(payload.get("payment_method")),
        account_from=_optional_text(payload.get("account_from")),
        account_to=_optional_text(payload.get("account_to")),
        card_name=_optional_text(payload.get("card_name")),
        is_recurring=bool(payload.get("is_recurring", False)),
        installment_total=int(payload["installment_total"])
        if payload.get("installment_total")
        else None,
        status=TransactionStatus(str(payload["status"])),
        confidence=float(payload["confidence"]),
    )


def _optional_text(value: object) -> str | None:
    return str(value) if value is not None else None


def _selected_record(
    repository: TransactionRepository, payload: dict[str, object], response: str
) -> TransactionRecord | None:
    if not response.isdigit():
        return None
    ids = payload.get("transaction_ids")
    if not isinstance(ids, list):
        return None
    index = int(response) - 1
    if index < 0 or index >= len(ids):
        return None
    return repository.get(str(ids[index]))


def _numbered_records(records: list[TransactionRecord]) -> str:
    return "\n".join(f"{index}. {_record_label(record)}" for index, record in enumerate(records, start=1))


def _record_label(record: TransactionRecord) -> str:
    return f"{record.transaction_date:%d/%m} - {record.description} - {format_money(record.amount)}"
