from functools import lru_cache

from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker

from finbot.core.settings import Settings
from finbot.db.base import Base


@lru_cache(maxsize=8)
def get_engine(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(
        database_url,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


@lru_cache(maxsize=8)
def _session_factory(database_url: str) -> sessionmaker:
    return sessionmaker(
        bind=get_engine(database_url),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )


def create_session_factory(settings: Settings) -> sessionmaker:
    return _session_factory(settings.database_url)


def create_database_schema(settings: Settings) -> None:
    engine = get_engine(settings.database_url)
    _run_migrations(engine)
    Base.metadata.create_all(bind=engine)


def _run_migrations(engine: Engine) -> None:
    config_path = Path("alembic.ini")
    if not config_path.exists():
        return
    from alembic import command
    from alembic.config import Config

    config = Config(str(config_path))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
