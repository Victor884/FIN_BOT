from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from finbot.db.base import Base
from finbot.db.repositories import TransactionRepository
from finbot.models.transaction import TransactionDraft, TransactionStatus, TransactionType


def make_session_factory() -> sessionmaker:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def make_draft() -> TransactionDraft:
    return TransactionDraft(
        type=TransactionType.EXPENSE,
        amount=Decimal("45.90"),
        transaction_date=date(2026, 7, 8),
        description="mercado",
        category="alimentacao",
        payment_method="pix",
        status=TransactionStatus.PAID,
        confidence=0.85,
    )


def test_repository_adds_and_gets_transaction() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        repository = TransactionRepository(session)
        record = repository.add(make_draft())
        session.commit()

        fetched = repository.get(record.id)

    assert fetched is not None
    assert fetched.id == record.id
    assert fetched.amount == Decimal("45.90")
    assert fetched.type == TransactionType.EXPENSE.value


def test_repository_lists_latest_transactions_first() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        repository = TransactionRepository(session)
        old_record = repository.add(make_draft())
        new_record = repository.add(
            TransactionDraft(
                type=TransactionType.INCOME,
                amount=Decimal("2500"),
                transaction_date=date(2026, 7, 9),
                description="salario",
                category="salario",
                status=TransactionStatus.RECEIVED,
            )
        )
        session.commit()

        records = repository.list()

    assert [record.id for record in records] == [new_record.id, old_record.id]


def test_record_round_trips_to_draft() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        repository = TransactionRepository(session)
        record = repository.add(make_draft())
        session.commit()

        draft = record.to_draft()

    assert draft.type == TransactionType.EXPENSE
    assert draft.amount == Decimal("45.90")
    assert draft.transaction_date == date(2026, 7, 8)
    assert draft.category == "alimentacao"
    assert draft.payment_method == "pix"
