from fastapi.testclient import TestClient

from finbot.api.app import create_app
from finbot.core.errors import ConfigurationError, FinbotError
from finbot.core.settings import Settings


def test_request_logging_adds_request_id_header() -> None:
    client = TestClient(create_app(Settings(log_level="INFO")))

    response = client.get("/health", headers={"X-Request-ID": "request-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "request-123"


def test_configuration_error_returns_safe_response() -> None:
    app = create_app(Settings(log_level="INFO"))

    @app.get("/raise-config")
    def raise_config() -> None:
        raise ConfigurationError("secret config detail")

    client = TestClient(app)

    response = client.get("/raise-config")

    assert response.status_code == 500
    assert response.json() == {
        "error": "configuration_error",
        "message": "Application is not configured.",
    }


def test_finbot_error_returns_safe_response() -> None:
    app = create_app(Settings(log_level="INFO"))

    @app.get("/raise-finbot")
    def raise_finbot() -> None:
        raise FinbotError("internal detail")

    client = TestClient(app)

    response = client.get("/raise-finbot")

    assert response.status_code == 400
    assert response.json() == {
        "error": "finbot_error",
        "message": "Could not process the request.",
    }
