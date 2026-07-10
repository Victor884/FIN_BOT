from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from finbot.api.dependencies.auth import require_admin
from finbot.api.dependencies.database import get_db
from finbot.api.dependencies.pagination import date_range
from finbot.api.schemas.common import ApiResponse
from finbot.api.schemas.dashboard import AdminSummaryData, CategoryPoint, IntegrationState, SeriesPoint
from finbot.db.models import UserRecord
from finbot.services.admin_dashboard_service import AdminDashboardService

router = APIRouter(prefix="/api/v1/admin/dashboard", tags=["admin dashboard"])


def _service(request: Request, session: Session) -> AdminDashboardService:
    return AdminDashboardService(session, request.app.state.settings)


@router.get("/summary", response_model=ApiResponse[AdminSummaryData])
def summary(
    request: Request,
    period: tuple[date, date] = Depends(date_range),
    _: UserRecord = Depends(require_admin),
    session: Session = Depends(get_db),
) -> ApiResponse[AdminSummaryData]:
    return ApiResponse(data=_service(request, session).summary(*period), request_id=request.state.request_id)


@router.get("/activity", response_model=ApiResponse[dict[str, object]])
def activity(
    request: Request,
    period: tuple[date, date] = Depends(date_range),
    _: UserRecord = Depends(require_admin),
    session: Session = Depends(get_db),
) -> ApiResponse[dict[str, object]]:
    return ApiResponse(data=_service(request, session).activity(*period), request_id=request.state.request_id)


@router.get("/users", response_model=ApiResponse[list[dict[str, object]]])
def users(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    _: UserRecord = Depends(require_admin),
    session: Session = Depends(get_db),
) -> ApiResponse[list[dict[str, object]]]:
    return ApiResponse(data=_service(request, session).users(limit), request_id=request.state.request_id)


@router.get("/transactions", response_model=ApiResponse[list[SeriesPoint]])
def transactions(
    request: Request,
    period: tuple[date, date] = Depends(date_range),
    user_id: str | None = None,
    transaction_type: str | None = Query(default=None, alias="type"),
    category: str | None = None,
    source: str | None = None,
    transaction_status: str | None = Query(default=None, alias="status"),
    _: UserRecord = Depends(require_admin),
    session: Session = Depends(get_db),
) -> ApiResponse[list[SeriesPoint]]:
    return ApiResponse(
        data=_service(request, session).transaction_series(
            *period,
            user_id=user_id,
            transaction_type=transaction_type,
            category=category,
            source=source,
            status=transaction_status,
        ),
        request_id=request.state.request_id,
    )


@router.get("/categories", response_model=ApiResponse[list[CategoryPoint]])
def categories(
    request: Request,
    period: tuple[date, date] = Depends(date_range),
    _: UserRecord = Depends(require_admin),
    session: Session = Depends(get_db),
) -> ApiResponse[list[CategoryPoint]]:
    return ApiResponse(data=_service(request, session).categories(*period), request_id=request.state.request_id)


@router.get("/performance", response_model=ApiResponse[dict[str, object]])
def performance(
    request: Request,
    period: tuple[date, date] = Depends(date_range),
    _: UserRecord = Depends(require_admin),
    session: Session = Depends(get_db),
) -> ApiResponse[dict[str, object]]:
    return ApiResponse(data=_service(request, session).performance(*period), request_id=request.state.request_id)


@router.get("/errors", response_model=ApiResponse[list[dict[str, object]]])
def errors(
    request: Request,
    period: tuple[date, date] = Depends(date_range),
    _: UserRecord = Depends(require_admin),
    session: Session = Depends(get_db),
) -> ApiResponse[list[dict[str, object]]]:
    return ApiResponse(data=_service(request, session).errors(*period), request_id=request.state.request_id)


@router.get("/integrations", response_model=ApiResponse[list[IntegrationState]])
def integrations(
    request: Request,
    _: UserRecord = Depends(require_admin),
    session: Session = Depends(get_db),
) -> ApiResponse[list[IntegrationState]]:
    return ApiResponse(data=_service(request, session).integrations(), request_id=request.state.request_id)
