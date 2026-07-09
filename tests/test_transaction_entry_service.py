from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from finbot.db.base import Base
from finbot.db.repositories import TransactionRepository
from finbot.parser.rules import RuleBasedParser
from finbot.services.transactions import TransactionEntryService, TransactionEntryStatus


def make_session_factory() -> sessionmaker:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def make_service(repository: TransactionRepository) -> TransactionEntryService:
    parser = RuleBasedParser(today_provider=lambda: date(2026, 7, 9))
    return TransactionEntryService(repository=repository, parser=parser)


def test_service_records_valid_transaction() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        repository = TransactionRepository(session)
        service = make_service(repository)

        result = service.record_from_text("Gastei R$ 45 no mercado hoje")
        records = repository.list()

    assert result.status == TransactionEntryStatus.RECORDED
    assert result.is_recorded
    assert result.transaction_id is not None
    assert result.validation is not None
    assert result.validation.is_valid
    assert len(records) == 1
    assert records[0].description == "mercado"


def test_service_returns_missing_fields_without_recording() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        repository = TransactionRepository(session)
        service = make_service(repository)

        result = service.record_from_text("Gastei no mercado hoje")
        records = repository.list()

    assert result.status == TransactionEntryStatus.NEEDS_MORE_INFO
    assert result.missing_fields == ("amount",)
    assert records == []


def test_service_returns_validation_errors_without_recording() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        repository = TransactionRepository(session)
        service = make_service(repository)

        result = service.record_from_text("Transferi R$ 500")
        records = repository.list()

    assert result.status == TransactionEntryStatus.INVALID
    assert result.validation is not None
    assert "account_from_required_for_transfer" in result.validation.errors
    assert "account_to_required_for_transfer" in result.validation.errors
    assert records == []


def test_service_records_valid_transaction_with_warning() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        repository = TransactionRepository(session)
        service = make_service(repository)

        result = service.record_from_text("Gastei R$ 10 hoje")
        records = repository.list()

    assert result.status == TransactionEntryStatus.RECORDED
    assert result.validation is not None
    assert result.validation.warnings == ("category_missing",)
    assert len(records) == 1


def test_service_rejects_duplicate_transaction() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        repository = TransactionRepository(session)
        service = make_service(repository)

        first_result = service.record_from_text("Gastei R$ 45 no mercado hoje")
        duplicate_result = service.record_from_text("Gastei R$ 45 no mercado hoje")
        records = repository.list()

    assert first_result.status == TransactionEntryStatus.RECORDED
    assert duplicate_result.status == TransactionEntryStatus.DUPLICATE
    assert duplicate_result.transaction_id == first_result.transaction_id
    assert len(records) == 1
