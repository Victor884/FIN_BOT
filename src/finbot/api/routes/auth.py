from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from finbot.api.dependencies.auth import get_current_user
from finbot.api.dependencies.database import get_db
from finbot.api.schemas.auth import (
    AuthUser,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TelegramLinkRequest,
    TokenPair,
)
from finbot.api.schemas.common import ApiResponse
from finbot.db.models import UserRecord
from finbot.services.auth import AuthService, AuthenticationError
from finbot.services.web_link import WebLinkError, WebLinkService

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


def _token_response(request: Request, access: str, refresh: str) -> ApiResponse[TokenPair]:
    settings = request.app.state.settings
    return ApiResponse(
        data=TokenPair(
            access_token=access,
            refresh_token=refresh,
            expires_in=settings.jwt_access_minutes * 60,
        ),
        request_id=request.state.request_id,
    )


@router.post("/register", response_model=ApiResponse[TokenPair], status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    session: Session = Depends(get_db),
) -> ApiResponse[TokenPair]:
    settings = request.app.state.settings
    if not settings.auth_allow_registration:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Registration is disabled")
    service = AuthService(session, settings)
    try:
        user = service.register(payload.name, payload.email, payload.password)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered") from exc
    return _token_response(request, *service.issue_tokens(user))


@router.post("/login", response_model=ApiResponse[TokenPair])
def login(
    payload: LoginRequest,
    request: Request,
    session: Session = Depends(get_db),
) -> ApiResponse[TokenPair]:
    service = AuthService(session, request.app.state.settings)
    try:
        user = service.authenticate(payload.email, payload.password)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials") from exc
    return _token_response(request, *service.issue_tokens(user))


@router.post("/telegram-link", response_model=ApiResponse[TokenPair])
def telegram_link(
    payload: TelegramLinkRequest,
    request: Request,
    session: Session = Depends(get_db),
) -> ApiResponse[TokenPair]:
    try:
        user = WebLinkService(session).exchange(
            payload.code, payload.email, payload.password, payload.name
        )
    except WebLinkError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Codigo de vinculacao invalido, expirado ou ja utilizado.",
        ) from exc
    return _token_response(
        request,
        *AuthService(session, request.app.state.settings).issue_tokens(user),
    )


@router.post("/refresh", response_model=ApiResponse[TokenPair])
def refresh(
    payload: RefreshRequest,
    request: Request,
    session: Session = Depends(get_db),
) -> ApiResponse[TokenPair]:
    service = AuthService(session, request.app.state.settings)
    try:
        _, access, refresh_token = service.refresh(payload.refresh_token)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session") from exc
    return _token_response(request, access, refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: RefreshRequest, request: Request, session: Session = Depends(get_db)) -> None:
    AuthService(session, request.app.state.settings).revoke(payload.refresh_token)


@router.get("/me", response_model=ApiResponse[AuthUser])
def me(request: Request, user: UserRecord = Depends(get_current_user)) -> ApiResponse[AuthUser]:
    return ApiResponse(
        data=AuthUser(id=user.id, name=user.name, email=user.email, role=user.role),
        request_id=request.state.request_id,
    )
