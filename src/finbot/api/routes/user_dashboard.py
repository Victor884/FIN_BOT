from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from finbot.api.dependencies.auth import get_current_user
from finbot.api.dependencies.database import get_db
from finbot.api.dependencies.pagination import date_range
from finbot.api.schemas.common import ApiResponse
from finbot.api.schemas.dashboard import CategoryPoint, FinancialSummaryData, SeriesPoint, TransactionItem, TransactionPage
from finbot.db.models import UserRecord
from finbot.services.user_dashboard_service import UserDashboardService

router = APIRouter(prefix="/api/v1/me", tags=["user dashboard"])


@router.get("/dashboard/summary", response_model=ApiResponse[FinancialSummaryData])
def summary(
    request: Request,
    period: tuple[date, date] = Depends(date_range),
    user: UserRecord = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> ApiResponse[FinancialSummaryData]:
    data = UserDashboardService(session, user.id).summary(*period)
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.get("/dashboard/cash-flow", response_model=ApiResponse[list[SeriesPoint]])
def cash_flow(
    request: Request,
    period: tuple[date, date] = Depends(date_range),
    user: UserRecord = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> ApiResponse[list[SeriesPoint]]:
    return ApiResponse(
        data=UserDashboardService(session, user.id).cash_flow(*period),
        request_id=request.state.request_id,
    )


@router.get("/dashboard/categories", response_model=ApiResponse[list[CategoryPoint]])
def categories(
    request: Request,
    period: tuple[date, date] = Depends(date_range),
    user: UserRecord = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> ApiResponse[list[CategoryPoint]]:
    return ApiResponse(
        data=UserDashboardService(session, user.id).categories(*period),
        request_id=request.state.request_id,
    )


@router.get("/transactions", response_model=ApiResponse[TransactionPage])
def transactions(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    start_date: date | None = None,
    end_date: date | None = None,
    category: str | None = None,
    transaction_type: str | None = Query(default=None, alias="type"),
    search: str | None = Query(default=None, max_length=100),
    transaction_status: str | None = Query(default=None, alias="status"),
    sort: str = Query(default="date_desc"),
    user: UserRecord = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> ApiResponse[TransactionPage]:
    data = UserDashboardService(session, user.id).transactions(
        page=page,
        page_size=page_size,
        start_date=start_date,
        end_date=end_date,
        category=category,
        transaction_type=transaction_type,
        search=search,
        status=transaction_status,
        sort=sort,
    )
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.get("/transactions/{transaction_id}", response_model=ApiResponse[TransactionItem])
def transaction_detail(
    transaction_id: str,
    request: Request,
    user: UserRecord = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> ApiResponse[TransactionItem]:
    item = UserDashboardService(session, user.id).get_transaction(transaction_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return ApiResponse(data=item, request_id=request.state.request_id)


@router.get("/pending-transactions", response_model=ApiResponse[TransactionPage])
def pending_transactions(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    user: UserRecord = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> ApiResponse[TransactionPage]:
    data = UserDashboardService(session, user.id).transactions(
        page=page, page_size=page_size, status="pending"
    )
    return ApiResponse(data=data, request_id=request.state.request_id)


@router.get("/export")
def export(
    user: UserRecord = Depends(get_current_user),
    session: Session = Depends(get_db),
    start_date: date | None = None,
    end_date: date | None = None,
) -> Response:
    csv_data = UserDashboardService(session, user.id).export_csv(start_date, end_date)
    return Response(
        content=csv_data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=finbot-transacoes.csv"},
    )
