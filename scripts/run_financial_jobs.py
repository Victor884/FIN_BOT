"""Run scheduled recurring entries, due balance effects and Supabase CSV backups."""

from finbot.core.metrics import apply_retention_policy
from finbot.core.settings import Settings
from finbot.db.models import UserRecord
from finbot.db.repositories import (
    AccountRepository,
    CardRepository,
    RecurringTransactionRepository,
    TransactionRepository,
)
from finbot.db.session import create_session_factory
from finbot.parser.factory import build_financial_parser
from finbot.services.backups import SupabaseBackupService
from finbot.services.recurrences import RecurringTransactionService
from finbot.services.transactions import TransactionEntryService


def main() -> None:
    settings = Settings()
    session_factory = create_session_factory(settings)
    with session_factory() as session:
        parser = build_financial_parser(settings)
        for user in session.query(UserRecord).filter(UserRecord.telegram_user_id.is_not(None)):
            transactions = TransactionRepository(session, user.id)
            service = TransactionEntryService(
                repository=transactions,
                parser=parser,
                account_repository=AccountRepository(session, user.id),
                card_repository=CardRepository(session, user.id),
                confirmation_threshold=settings.transaction_confirmation_threshold,
            )
            RecurringTransactionService(RecurringTransactionRepository(session, user.id), service).generate_due()
            service.apply_due_transactions()
        backup_count = SupabaseBackupService(settings).backup_all_users(session)
        apply_retention_policy(session, settings.metrics_retention_days)
        session.commit()
    print(f"financial jobs completed; backups={backup_count}")


if __name__ == "__main__":
    main()
