from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from finbot.db.base import Base
from finbot.db.repositories import TransactionRepository
from finbot.models.transaction import TransactionDraft, TransactionStatus, TransactionType
from finbot.services.deduplication import build_transaction_dedupe_key
from finbot.services.queries import FinancialQueryService


def make_session_factory() -> sessionmaker:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def add_transaction(repository: TransactionRepository, draft: TransactionDraft) -> None:
    repository.add(draft, dedupe_key=build_transaction_dedupe_key(draft))


def make_draft(
    transaction_type: TransactionType,
    amount: str,
    transaction_date: date,
    description: str,
    category: str | None,
    status: TransactionStatus,
) -> TransactionDraft:
    return TransactionDraft(
        type=transaction_type,
        amount=Decimal(amount),
        transaction_date=transaction_date,
        description=description,
        category=category,
        status=status,
    )


def seed_transactions(repository: TransactionRepository) -> None:
    add_transaction(
        repository,
        make_draft(
            TransactionType.INCOME,
            "2500",
            date(2026, 7, 5),
            "salario",
            "salario",
            TransactionStatus.RECEIVED,
        ),
    )
    add_transaction(
        repository,
        make_draft(
            TransactionType.EXPENSE,
            "45",
            date(2026, 7, 9),
            "mercado",
            "alimentacao",
            TransactionStatus.PAID,
        ),
    )
    add_transaction(
        repository,
        make_draft(
            TransactionType.EXPENSE,
            "120",
            date(2026, 7, 10),
            "internet",
            "moradia",
            TransactionStatus.PENDING,
        ),
    )
    add_transaction(
        repository,
        make_draft(
            TransactionType.EXPENSE,
            "80",
            date(2026, 6, 30),
            "farmacia",
            "saude",
            TransactionStatus.PAID,
        ),
    )


def test_monthly_summary_calculates_totals_and_balance() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        repository = TransactionRepository(session)
        seed_transactions(repository)
        service = FinancialQueryService(repository)

        summary = service.monthly_summary(2026, 7)

    assert summary.total_income == Decimal("2500.00")
    assert summary.total_expenses == Decimal("165.00")
    assert summary.balance == Decimal("2335.00")
    assert summary.pending_total == Decimal("120.00")
    assert summary.expenses_by_category == {
        "alimentacao": Decimal("45.00"),
        "moradia": Decimal("120.00"),
    }
    assert [record.description for record in summary.largest_expenses] == ["internet", "mercado"]


def test_total_expenses_by_category_filters_period() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        repository = TransactionRepository(session)
        seed_transactions(repository)
        service = FinancialQueryService(repository)

        total = service.total_expenses_by_category(
            "alimentacao", date(2026, 7, 1), date(2026, 7, 31)
        )

    assert total == Decimal("45.00")


def test_pending_transactions_returns_pending_records() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        repository = TransactionRepository(session)
        seed_transactions(repository)
        service = FinancialQueryService(repository)

        pending = service.pending_transactions()

    assert len(pending) == 1
    assert pending[0].description == "internet"


def test_weekly_summary_uses_monday_to_sunday() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        repository = TransactionRepository(session)
        seed_transactions(repository)
        service = FinancialQueryService(repository)

        summary = service.weekly_summary(date(2026, 7, 9))

    assert summary.start_date == date(2026, 7, 6)
    assert summary.end_date == date(2026, 7, 12)
    assert summary.total_income == Decimal("0")
    assert summary.total_expenses == Decimal("165.00")
