import asyncio
import logging

import httpx
from fastapi.testclient import TestClient

from finbot.ai.groq_service import GroqCompletion, GroqService, GroqUnavailableError
from finbot.api.app import create_app
from finbot.core.security import create_access_token, hash_password
from finbot.core.settings import Settings
from finbot.db.models import UserRecord


def test_groq_service_returns_structured_completion(caplog) -> None:  # type: ignore[no-untyped-def]
    prompt = "conteudo-financeiro-confidencial"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/openai/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(
            200,
            json={
                "model": "llama-3.1-8b-instant",
                "choices": [{"message": {"content": "Resposta curta."}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13},
            },
        )

    async def run() -> GroqCompletion:
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.groq.test",
        )
        service = GroqService(
            api_key="test-key",
            model="llama-3.1-8b-instant",
            base_url="https://api.groq.test/openai/v1",
            timeout_seconds=1,
            max_output_tokens=100,
            client=client,
        )
        try:
            return await service.complete(prompt, "user-1")
        finally:
            await service.close()

    with caplog.at_level(logging.INFO):
        result = asyncio.run(run())

    assert result.text == "Resposta curta."
    assert result.total_tokens == 13
    assert prompt not in caplog.text


def test_groq_service_converts_timeout_to_friendly_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    async def run() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        service = GroqService(
            api_key="test-key",
            model="llama-3.1-8b-instant",
            base_url="https://api.groq.test/openai/v1",
            timeout_seconds=1,
            max_output_tokens=100,
            client=client,
        )
        try:
            await service.complete("teste", "user-1")
        finally:
            await service.close()

    try:
        asyncio.run(run())
    except GroqUnavailableError as exc:
        assert "demorou" in str(exc)
    else:
        raise AssertionError("GroqUnavailableError was not raised")


class FakeGroqService:
    async def complete(self, prompt: str, user_id: str) -> GroqCompletion:
        return GroqCompletion(text=f"Resposta para {len(prompt)} caracteres.", model="fake-model")


def test_groq_endpoint_is_authenticated_and_rate_limited(tmp_path) -> None:  # type: ignore[no-untyped-def]
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'groq.db'}",
        jwt_secret="test-secret-with-at-least-32-characters",
        telegram_bot_token=None,
        telegram_webhook_secret=None,
        google_sheets_spreadsheet_id=None,
        google_service_account_file=None,
        groq_api_key=None,
        groq_requests_per_minute=1,
    )
    app = create_app(settings)
    app.state.groq_service = FakeGroqService()
    with app.state.session_factory() as session:
        user = UserRecord(
            name="Teste",
            email="groq@example.com",
            password_hash=hash_password("strong-password"),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        token = create_access_token(user.id, user.role, settings)

    client = TestClient(app)
    unauthorized = client.post("/api/v1/ai/completions", json={"prompt": "teste"})
    assert unauthorized.status_code == 401

    headers = {"Authorization": f"Bearer {token}"}
    first = client.post("/api/v1/ai/completions", json={"prompt": "teste"}, headers=headers)
    second = client.post("/api/v1/ai/completions", json={"prompt": "teste"}, headers=headers)

    assert first.status_code == 200
    assert first.json()["data"]["model"] == "fake-model"
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "RATE_LIMITED"
