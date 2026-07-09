from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from finbot.core.settings import Settings
from finbot.db.base import Base


def create_session_factory(settings: Settings) -> sessionmaker:
    engine = create_engine(settings.database_url, future=True)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def create_database_schema(settings: Settings) -> None:
    engine = create_engine(settings.database_url, future=True)
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns(engine)


def _ensure_sqlite_columns(engine) -> None:  # type: ignore[no-untyped-def]
    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "transactions" not in table_names:
        return

    transaction_columns = {column["name"] for column in inspector.get_columns("transactions")}
    with engine.begin() as connection:
        if "card_name" not in transaction_columns:
            connection.execute(text("ALTER TABLE transactions ADD COLUMN card_name VARCHAR(120)"))
