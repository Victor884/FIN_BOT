from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class FinancialSummaryData(BaseModel):
    start_date: date
    end_date: date
    income: Decimal
    expenses: Decimal
    balance: Decimal
    transaction_count: int
    daily_expense_average: Decimal
    largest_expense: Decimal
    top_expense_category: str | None
    pending_expenses: Decimal
    previous_period_balance: Decimal
    balance_change_percent: Decimal | None


class SeriesPoint(BaseModel):
    label: str
    income: Decimal = Decimal("0")
    expenses: Decimal = Decimal("0")
    balance: Decimal = Decimal("0")
    count: int = 0


class CategoryPoint(BaseModel):
    category: str
    amount: Decimal
    count: int


class TransactionItem(BaseModel):
    id: str
    type: str
    amount: Decimal
    transaction_date: date
    description: str
    category: str | None
    account_from: str | None
    account_to: str | None
    payment_method: str | None
    status: str
    source: str
    sheets_synced: bool
    needs_confirmation: bool
    is_recurring: bool
    installment_group_id: str | None = None
    installment_number: int | None = None
    installment_total: int | None = None
    created_at: datetime


class TransactionPage(BaseModel):
    items: list[TransactionItem]
    page: int
    page_size: int
    total: int
    pages: int


class AdminSummaryData(BaseModel):
    users_total: int
    users_active_today: int
    users_active_7d: int
    users_active_30d: int
    new_users: int
    messages_total: int
    transactions_total: int
    income_count: int
    expense_count: int
    transfer_count: int
    income_amount: Decimal
    expense_amount: Decimal
    aggregate_balance: Decimal
    local_parser_messages: int
    ai_parser_messages: int
    ai_usage_rate: Decimal
    parser_success_rate: Decimal
    error_rate: Decimal
    response_time_average_ms: Decimal
    response_time_p50_ms: int
    response_time_p95_ms: int
    response_time_p99_ms: int
    duplicates_blocked: int


class IntegrationState(BaseModel):
    name: str
    status: str
    latency_ms: int | None = None
    message: str | None = None


class PublicConfig(BaseModel):
    api_version: str
    environment: str
    registration_enabled: bool
    features: dict[str, bool] = Field(default_factory=dict)
