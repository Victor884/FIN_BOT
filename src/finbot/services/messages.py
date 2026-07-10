import logging
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from finbot.db.models import TransactionRecord
from finbot.db.repositories import AccountRepository, CardRepository, TransactionRepository
from finbot.models.transaction import TransactionType
from finbot.services.accounts import AccountService, format_money
from finbot.services.cards import CardService
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
    ) -> None:
        self._transaction_service = transaction_service
        self._transaction_repository = transaction_repository
        self._account_repository = account_repository
        self._card_repository = card_repository
        self._account_service = AccountService(account_repository)
        self._card_service = CardService(card_repository, account_repository) if card_repository else None

    def bind_user(self, user_id: str) -> None:
        """Scope all repositories in this request to the authenticated Telegram user."""
        self._transaction_repository.user_id = user_id
        self._account_repository.user_id = user_id
        if self._card_repository is not None:
            self._card_repository.user_id = user_id

    @property
    def session(self):  # type: ignore[no-untyped-def]
        return self._transaction_repository._session

    def handle_text(self, text: str) -> BotMessageResult:
        stripped = text.strip()
        if stripped.startswith("/"):
            return self._handle_command(stripped)

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
            return BotMessageResult(status="categories", message=categories_message())
        if command == "/ultimos":
            return BotMessageResult(status="recent", message=self._recent_transactions(args))
        if command == "/resumo":
            return BotMessageResult(status="summary", message=self._quick_month_summary())
        if command == "/pendentes":
            return BotMessageResult(status="pending", message=self._pending_transactions())
        if command == "/exportar":
            return BotMessageResult(status="export", message=export_message())
        if command == "/cancelar":
            return BotMessageResult(status="cancelled", message="Operacao pendente cancelada.")
        if command == "/editar":
            return BotMessageResult(
                status="edit_not_available",
                message="Edicao interativa ainda nao esta habilitada. Use /ultimos para localizar o lancamento.",
            )
        if command == "/excluir":
            return BotMessageResult(
                status="delete_not_available",
                message="Exclusao interativa ainda nao esta habilitada. Use /ultimos para localizar o lancamento.",
            )
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
        "- /addconta Banco Inter banco saldo 1000\n"
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
        "A sincronizacao com Google Sheets acontece automaticamente a cada novo lancamento. "
        "Para recriar abas e formulas, execute o setup da planilha no backend."
    )
