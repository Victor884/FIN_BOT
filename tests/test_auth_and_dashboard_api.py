from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from finbot.api.app import create_app
from finbot.core.security import create_access_token, hash_password
from finbot.core.settings import Settings
from finbot.db.models import TransactionRecord, UserRecord
from finbot.db.repositories import UserRepository
from finbot.models.transaction import TransactionDraft, TransactionStatus, TransactionType
from finbot.services.web_link import WebLinkService


def make_app(tmp_path, **overrides):  # type: ignore[no-untyped-def]
    values = {
        "database_url": f"sqlite:///{tmp_path / 'api.db'}",
        "jwt_secret": "test-secret-with-enough-entropy",
        "telegram_bot_token": None,
        "google_sheets_spreadsheet_id": None,
        "google_service_account_file": None,
        "cors_allowed_origins": "http://localhost:5173,https://finbot.lovable.app",
    }
    values.update(overrides)
    return create_app(Settings(**values))


def add_user(app, email: str, role: str = "USER") -> UserRecord:  # type: ignore[no-untyped-def]
    with app.state.session_factory() as session:
        user = UserRecord(
            name=email.split("@")[0],
            email=email,
            password_hash=hash_password("strong-password"),
            role=role,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def token_for(app, user: UserRecord) -> str:  # type: ignore[no-untyped-def]
    return create_access_token(user.id, user.role, app.state.settings)


def add_transaction(
    app, user_id: str, transaction_type: TransactionType, amount: str, description: str
) -> TransactionRecord:  # type: ignore[no-untyped-def]
    draft = TransactionDraft(
        type=transaction_type,
        amount=Decimal(amount),
        transaction_date=date.today(),
        description=description,
        category="alimentacao" if transaction_type == TransactionType.EXPENSE else "salario",
        status=(
            TransactionStatus.PAID
            if transaction_type == TransactionType.EXPENSE
            else TransactionStatus.RECEIVED
        ),
    )
    with app.state.session_factory() as session:
        record = TransactionRecord.from_draft(
            draft,
            dedupe_key=f"{user_id}-{description}",
            user_id=user_id,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record


def test_login_refresh_and_me(tmp_path) -> None:  # type: ignore[no-untyped-def]
    app = make_app(tmp_path)
    user = add_user(app, "user@example.com")
    client = TestClient(app)

    login = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "strong-password"},
    )
    assert login.status_code == 200
    tokens = login.json()["data"]

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["data"]["id"] == user.id

    refreshed = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["data"]["refresh_token"] != tokens["refresh_token"]


def test_admin_endpoint_requires_admin_role(tmp_path) -> None:  # type: ignore[no-untyped-def]
    app = make_app(tmp_path)
    user = add_user(app, "user@example.com")
    client = TestClient(app)

    response = client.get(
        "/api/v1/admin/dashboard/summary",
        headers={"Authorization": f"Bearer {token_for(app, user)}"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    assert "request_id" in response.json()


def test_user_dashboard_isolates_financial_data(tmp_path) -> None:  # type: ignore[no-untyped-def]
    app = make_app(tmp_path)
    first = add_user(app, "first@example.com")
    second = add_user(app, "second@example.com")
    add_transaction(app, first.id, TransactionType.INCOME, "1000", "salario")
    add_transaction(app, first.id, TransactionType.EXPENSE, "125.50", "mercado")
    add_transaction(app, second.id, TransactionType.EXPENSE, "900", "outro usuario")
    client = TestClient(app)

    response = client.get(
        "/api/v1/me/dashboard/summary",
        headers={"Authorization": f"Bearer {token_for(app, first)}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert Decimal(data["income"]) == Decimal("1000")
    assert Decimal(data["expenses"]) == Decimal("125.50")
    assert Decimal(data["balance"]) == Decimal("874.50")
    assert data["transaction_count"] == 2


def test_transaction_detail_cannot_cross_user_boundary(tmp_path) -> None:  # type: ignore[no-untyped-def]
    app = make_app(tmp_path)
    first = add_user(app, "first@example.com")
    second = add_user(app, "second@example.com")
    record = add_transaction(app, second.id, TransactionType.EXPENSE, "50", "privado")
    client = TestClient(app)

    response = client.get(
        f"/api/v1/me/transactions/{record.id}",
        headers={"Authorization": f"Bearer {token_for(app, first)}"},
    )

    assert response.status_code == 404


def test_transaction_pagination_and_empty_state(tmp_path) -> None:  # type: ignore[no-untyped-def]
    app = make_app(tmp_path)
    user = add_user(app, "user@example.com")
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token_for(app, user)}"}

    empty = client.get("/api/v1/me/transactions", headers=headers)
    assert empty.json()["data"] == {
        "items": [], "page": 1, "page_size": 25, "total": 0, "pages": 0
    }

    for index in range(3):
        add_transaction(app, user.id, TransactionType.EXPENSE, str(index + 1), f"item-{index}")
    page = client.get("/api/v1/me/transactions?page=2&page_size=2", headers=headers)
    assert page.json()["data"]["total"] == 3
    assert len(page.json()["data"]["items"]) == 1


def test_health_and_cors_contracts(tmp_path) -> None:  # type: ignore[no-untyped-def]
    app = make_app(tmp_path)
    client = TestClient(app)

    ready = client.get("/health/ready")
    assert ready.json()["database"] == "available"

    allowed = client.options(
        "/api/v1/config/public",
        headers={
            "Origin": "https://finbot.lovable.app",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "https://finbot.lovable.app"

    denied = client.options(
        "/api/v1/config/public",
        headers={"Origin": "https://unknown.example", "Access-Control-Request-Method": "GET"},
    )
    assert denied.status_code == 400


def test_telegram_link_connects_web_login_to_existing_user(tmp_path) -> None:  # type: ignore[no-untyped-def]
    app = make_app(tmp_path)
    with app.state.session_factory() as session:
        user = UserRepository(session).get_or_create_telegram(
            telegram_user_id=123,
            chat_id=123,
            name="Usuario Telegram",
            username="telegram_user",
        )
        code = WebLinkService(session).create_code(user.id)
        user_id = user.id
        session.commit()

    client = TestClient(app)
    linked = client.post(
        "/api/v1/auth/telegram-link",
        json={
            "code": code,
            "email": "telegram@example.com",
            "password": "strong-password",
        },
    )
    assert linked.status_code == 200
    access = linked.json()["data"]["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.json()["data"]["id"] == user_id

    reused = client.post(
        "/api/v1/auth/telegram-link",
        json={
            "code": code,
            "email": "telegram@example.com",
            "password": "strong-password",
        },
    )
    assert reused.status_code == 400
