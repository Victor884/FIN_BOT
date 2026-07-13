"""Apply migrations and create the optional bootstrap admin explicitly."""

from finbot.core.settings import Settings
from finbot.db.session import bootstrap_database, create_session_factory
from finbot.services.auth import bootstrap_admin


def main() -> None:
    settings = Settings()
    bootstrap_database(settings)
    with create_session_factory(settings)() as session:
        bootstrap_admin(session, settings)
        session.commit()


if __name__ == "__main__":
    main()
