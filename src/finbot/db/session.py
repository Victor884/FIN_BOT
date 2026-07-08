from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from finbot.core.settings import Settings


def create_session_factory(settings: Settings) -> sessionmaker:
    engine = create_engine(settings.database_url, future=True)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

