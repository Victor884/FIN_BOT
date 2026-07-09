from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from finbot.db.base import Base
from finbot.db.repositories import AccountRepository, CardRepository, TransactionRepository
from finbot.parser.rules import RuleBasedParser
from finbot.services.messages import BotMessageService, split_financial_entries
from finbot.services.transactions import TransactionEntryService


def make_service() -> tuple[BotMessageService, AccountRepository, TransactionRepository, CardRepository]:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = session_factory()
    account_repository = AccountRepository(session)
    card_repository = CardRepository(session)
    transaction_repository = TransactionRepository(session)
    parser = RuleBasedParser(today_provider=lambda: date(2026, 7, 9))
    transaction_service = TransactionEntryService(
        repository=transaction_repository,
        parser=parser,
        account_repository=account_repository,
        card_repository=card_repository,
    )
    return (
        BotMessageService(
            transaction_service=transaction_service,
            transaction_repository=transaction_repository,
            account_repository=account_repository,
            card_repository=card_repository,
        ),
        account_repository,
        transaction_repository,
        card_repository,
    )


def test_add_and_list_accounts() -> None:
    service, _, _, _ = make_service()

    add_message = service.handle_text("/addconta Banco Inter banco saldo 1000").message
    list_message = service.handle_text("/contas").message

    assert "Conta cadastrada: Banco Inter" in add_message
    assert "Banco Inter: R$ 1000,00" in list_message
    assert "Saldo total: R$ 1000,00" in list_message


def test_add_account_from_natural_text_with_name_and_balance() -> None:
    service, account_repository, _, _ = make_service()

    message = service.handle_text("Crie uma conta chamada Banco Inter com saldo inicial de R$ 500").message
    account = account_repository.get_by_name("Banco Inter")

    assert message == "Conta cadastrada: Banco Inter com saldo R$ 500,00."
    assert account is not None
    assert account.type == "banco"
    assert account.current_balance.to_eng_string() == "500.00"


def test_add_wallet_from_natural_balance_sentence() -> None:
    service, account_repository, _, _ = make_service()

    message = service.handle_text("Tenho R$ 300 no Mercado Pago").message
    account = account_repository.get_by_name("Mercado Pago")

    assert message == "Conta cadastrada: Mercado Pago com saldo R$ 300,00."
    assert account is not None
    assert account.type == "carteira"


def test_add_account_from_natural_text_asks_missing_balance() -> None:
    service, account_repository, _, _ = make_service()

    result = service.handle_text("Criar conta Nubank")

    assert result.status == "account_added"
    assert result.message == "Qual e o saldo inicial da conta Nubank?"
    assert account_repository.list() == []


def test_balance_general_and_by_account() -> None:
    service, _, _, _ = make_service()
    service.handle_text("/addconta Banco Inter banco saldo 1000")
    service.handle_text("/addconta Nubank banco saldo 500")

    assert service.handle_text("/saldo").message == "Saldo total: R$ 1500,00."
    assert service.handle_text("/saldo inter").message == "Saldo de Banco Inter: R$ 1000,00."


def test_add_and_list_credit_card() -> None:
    service, _, _, card_repository = make_service()
    service.handle_text("/addconta Nubank banco saldo 500")

    message = service.handle_text("/addcartao Nubank credito conta Nubank limite 2000").message
    cards_message = service.handle_text("/cartoes").message
    card = card_repository.get_by_name("Cartao Nubank")

    assert message == "Cartao cadastrado: Cartao Nubank credito vinculado a Nubank."
    assert card is not None
    assert card.limit.to_eng_string() == "2000.00"
    assert "Cartao Nubank: credito vinculado a Nubank - fatura R$ 0,00" in cards_message


def test_add_debit_card_from_natural_text() -> None:
    service, _, _, card_repository = make_service()
    service.handle_text("/addconta Banco Inter banco saldo 1000")

    message = service.handle_text("Adicionar cartao Inter debito associado ao Banco Inter").message
    card = card_repository.get_by_name("Cartao Inter")

    assert message == "Cartao cadastrado: Cartao Inter debito vinculado a Banco Inter."
    assert card is not None
    assert card.type == "debito"


def test_credit_card_expense_increases_invoice_without_changing_balance() -> None:
    service, account_repository, transaction_repository, card_repository = make_service()
    service.handle_text("/addconta Nubank banco saldo 500")
    service.handle_text("/addcartao Nubank credito conta Nubank limite 2000")

    result = service.handle_text("Gastei R$ 120 no mercado no cartao Nubank credito")
    card = card_repository.get_by_name("Cartao Nubank")
    account = account_repository.get_by_name("Nubank")
    record = transaction_repository.list()[0]

    assert result.status == "recorded"
    assert card is not None
    assert card.current_invoice.to_eng_string() == "120.00"
    assert account is not None
    assert account.current_balance.to_eng_string() == "500.00"
    assert record.card_name == "Cartao Nubank"
    assert record.payment_method == "cartao_credito"


def test_debit_card_expense_changes_linked_account_balance() -> None:
    service, account_repository, _, _ = make_service()
    service.handle_text("/addconta Banco Inter banco saldo 1000")
    service.handle_text("/addcartao Inter debito conta Banco Inter")

    service.handle_text("Gastei R$ 80 no mercado no cartao Inter debito")
    account = account_repository.get_by_name("Banco Inter")

    assert account is not None
    assert account.current_balance.to_eng_string() == "920.00"


def test_pay_credit_card_invoice() -> None:
    service, account_repository, _, card_repository = make_service()
    service.handle_text("/addconta Nubank banco saldo 500")
    service.handle_text("/addconta Banco Inter banco saldo 1000")
    service.handle_text("/addcartao Nubank credito conta Nubank limite 2000")
    service.handle_text("Gastei R$ 120 no mercado no cartao Nubank credito")

    message = service.handle_text("Paguei fatura Nubank R$ 50 com Banco Inter").message
    card = card_repository.get_by_name("Cartao Nubank")
    account = account_repository.get_by_name("Banco Inter")

    assert message == (
        "Pagamento de fatura registrado: R$ 50,00 do cartao Cartao Nubank, "
        "pago pela conta Banco Inter."
    )
    assert card is not None
    assert card.current_invoice.to_eng_string() == "70.00"
    assert account is not None
    assert account.current_balance.to_eng_string() == "950.00"


def test_transfer_with_explicit_origin_and_destination_updates_balances() -> None:
    service, account_repository, transaction_repository, _ = make_service()
    service.handle_text("/addconta Banco Inter banco saldo 1000")
    service.handle_text("/addconta Mercado Pago carteira saldo 100")

    result = service.handle_text("Transferi R$ 60 do banco Inter para a carteira do Mercado Pago")
    accounts = {account.name: account.current_balance for account in account_repository.list()}
    records = transaction_repository.list()

    assert result.status == "recorded"
    assert "Transferencia registrada" in result.message
    assert records[0].account_from == "Banco Inter"
    assert records[0].account_to == "Mercado Pago"
    assert accounts["Banco Inter"].to_eng_string() == "940.00"
    assert accounts["Mercado Pago"].to_eng_string() == "160.00"


def test_transfer_without_origin_asks_only_origin() -> None:
    service, _, transaction_repository, _ = make_service()
    service.handle_text("/addconta Poupanca poupanca saldo 0")

    result = service.handle_text("Mandei R$ 400 para a poupanca hoje")

    assert result.status == "needs_more_info"
    assert result.message == (
        "Entendi que e uma transferencia de R$ 400,00 para Poupanca. "
        "De qual conta saiu esse valor?"
    )
    assert transaction_repository.list() == []


def test_ambiguous_wallet_transfer_asks_destination() -> None:
    service, _, transaction_repository, _ = make_service()
    service.handle_text("/addconta Mercado Pago carteira saldo 0")
    service.handle_text("/addconta Carteira fisica carteira saldo 0")

    result = service.handle_text("Transferi R$ 75 para minha carteira digital")

    assert result.status == "needs_more_info"
    assert "qual conta" in result.message
    assert "Mercado Pago" in result.message
    assert "Carteira fisica" in result.message
    assert transaction_repository.list() == []


def test_multiple_entries_by_newline_are_recorded_separately() -> None:
    service, _, transaction_repository, _ = make_service()

    result = service.handle_text(
        "Gastei R$ 45 no mercado, categoria alimentacao\n"
        "Paguei R$ 120 de internet, categoria moradia\n"
        "Gastei R$ 80 com Uber, categoria transporte"
    )
    records = transaction_repository.list()

    assert result.status == "batch_processed"
    assert len(records) == 3
    assert "Registrei 3 lancamentos" in result.message
    assert all("internet, categoria moradia 80" not in record.description for record in records)


def test_multiple_entries_by_pipe_and_semicolon_are_split() -> None:
    pipe_items = split_financial_entries(
        "Gastei R$ 45 no mercado | Paguei R$ 120 de internet | Recebi R$ 300 de freelance"
    )
    semicolon_items = split_financial_entries(
        "Gastei R$ 45 no mercado; Paguei R$ 120 de internet; Recebi R$ 300 de freelance"
    )

    assert len(pipe_items) == 3
    assert len(semicolon_items) == 3


def test_invalid_message_returns_friendly_help() -> None:
    service, _, _, _ = make_service()

    result = service.handle_text("v")

    assert result.status == "needs_more_info"
    assert "Nao consegui entender" in result.message
    assert "type" not in result.message
    assert "amount" not in result.message


def test_recent_transactions_command() -> None:
    service, _, _, _ = make_service()
    service.handle_text("Gastei R$ 45 no mercado hoje")

    result = service.handle_text("/ultimos 10")

    assert result.status == "recent"
    assert "Ultimos 1 lancamentos:" in result.message
    assert "mercado" in result.message


def test_pending_transactions_command() -> None:
    service, _, _, _ = make_service()
    service.handle_text("Vou pagar R$ 120 de internet")

    result = service.handle_text("/pendentes")

    assert result.status == "pending"
    assert "Despesas pendentes:" in result.message
    assert "internet" in result.message


def test_summary_and_export_commands() -> None:
    service, _, _, _ = make_service()
    service.handle_text("Gastei R$ 45 no mercado hoje")
    service.handle_text("Recebi R$ 100 de freelance")

    summary = service.handle_text("/resumo")
    export = service.handle_text("/exportar")

    assert summary.status == "summary"
    assert "Resumo do mes:" in summary.message
    assert "Receitas:" in summary.message
    assert export.status == "export"
    assert "Google Sheets" in export.message


def test_cancel_edit_delete_commands_are_friendly() -> None:
    service, _, _, _ = make_service()

    assert service.handle_text("/cancelar").message == "Operacao pendente cancelada."
    assert "ainda nao esta habilitada" in service.handle_text("/editar").message
    assert "ainda nao esta habilitada" in service.handle_text("/excluir").message
