from datetime import date
from decimal import Decimal

from finbot.models.transaction import TransactionStatus, TransactionType
from finbot.parser.rules import RuleBasedParser


def make_parser() -> RuleBasedParser:
    return RuleBasedParser(today_provider=lambda: date(2026, 7, 8))


def test_parse_expense_with_category_and_today() -> None:
    result = make_parser().parse("Gastei R$ 45 no mercado hoje")

    assert result.draft is not None
    assert result.missing_fields == ()
    assert result.draft.type == TransactionType.EXPENSE
    assert result.draft.amount == Decimal("45")
    assert result.draft.transaction_date == date(2026, 7, 8)
    assert result.draft.category == "alimentacao"
    assert result.draft.status == TransactionStatus.PAID


def test_parse_income_with_received_status() -> None:
    result = make_parser().parse("Recebi R$ 2.500 de salario")

    assert result.draft is not None
    assert result.draft.type == TransactionType.INCOME
    assert result.draft.amount == Decimal("2500")
    assert result.draft.category == "receita_fixa"
    assert result.draft.status == TransactionStatus.RECEIVED


def test_parse_expense_with_payment_method_and_pending_status() -> None:
    result = make_parser().parse("Vou pagar R$ 120 de internet no cartao de credito")

    assert result.draft is not None
    assert result.draft.type == TransactionType.EXPENSE
    assert result.draft.amount == Decimal("120")
    assert result.draft.category == "moradia"
    assert result.draft.payment_method == "cartao_credito"
    assert result.draft.status == TransactionStatus.PENDING


def test_parse_transfer_between_accounts() -> None:
    result = make_parser().parse("Transferi R$ 500 da conta corrente para a poupanca")

    assert result.draft is not None
    assert result.draft.type == TransactionType.TRANSFER
    assert result.draft.amount == Decimal("500")
    assert result.draft.account_from == "conta corrente"
    assert result.draft.account_to == "poupanca"


def test_parse_transfer_between_named_accounts() -> None:
    result = make_parser().parse("Transferi R$ 60 do banco Inter para a carteira do Mercado Pago")

    assert result.draft is not None
    assert result.draft.type == TransactionType.TRANSFER
    assert result.draft.amount == Decimal("60")
    assert result.draft.account_from == "banco inter"
    assert result.draft.account_to == "carteira do mercado pago"


def test_parse_transfer_with_only_destination() -> None:
    result = make_parser().parse("Mandei R$ 400 para a poupanca hoje")

    assert result.draft is not None
    assert result.draft.type == TransactionType.TRANSFER
    assert result.draft.amount == Decimal("400")
    assert result.draft.account_from is None
    assert result.draft.account_to == "poupanca"


def test_parse_absolute_day_and_description() -> None:
    result = make_parser().parse("Paguei R$ 120 de internet dia 05/07")

    assert result.draft is not None
    assert result.draft.type == TransactionType.EXPENSE
    assert result.draft.amount == Decimal("120")
    assert result.draft.description == "internet"
    assert result.draft.transaction_date == date(2026, 7, 5)


def test_parse_restaurant_on_saturday() -> None:
    result = make_parser().parse("Gastei R$ 80 com restaurante no sabado")

    assert result.draft is not None
    assert result.draft.type == TransactionType.EXPENSE
    assert result.draft.category == "alimentacao"


def test_parse_lunch_decimal_expense() -> None:
    result = make_parser().parse("comprei um almoco R$ 32,99")

    assert result.draft is not None
    assert result.draft.type == TransactionType.EXPENSE
    assert result.draft.amount == Decimal("32.99")
    assert result.draft.category == "alimentacao"


def test_parse_yesterday() -> None:
    result = make_parser().parse("Comprei 35,90 na farmacia ontem")

    assert result.draft is not None
    assert result.draft.amount == Decimal("35.90")
    assert result.draft.transaction_date == date(2026, 7, 7)
    assert result.draft.category == "saude"


def test_parse_accented_input() -> None:
    result = make_parser().parse("Paguei R$ 80 de farmácia no cartão de crédito")

    assert result.draft is not None
    assert result.draft.category == "saude"
    assert result.draft.payment_method == "cartao_credito"


def test_missing_amount_returns_missing_fields() -> None:
    result = make_parser().parse("Gastei no mercado hoje")

    assert result.draft is None
    assert result.missing_fields == ("amount",)
