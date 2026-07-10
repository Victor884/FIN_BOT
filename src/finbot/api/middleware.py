import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from starlette.background import BackgroundTask, BackgroundTasks

from finbot.db.models import ApplicationErrorRecord, RequestMetricRecord


logger = logging.getLogger(__name__)


def register_request_logging(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        start = perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (perf_counter() - start) * 1000
            logger.exception(
                "request_failed request_id=%s method=%s path=%s elapsed_ms=%.2f",
                request_id,
                request.method,
                request.url.path,
                elapsed_ms,
            )
            raise

        elapsed_ms = (perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_completed request_id=%s method=%s path=%s status_code=%s elapsed_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        metric_task = BackgroundTask(
            _persist_request_metric,
            app.state.session_factory,
            request_id,
            getattr(request.state, "user_id", None),
            request.url.path,
            request.method,
            response.status_code,
            round(elapsed_ms),
            "telegram" if request.url.path.startswith("/telegram") else "web",
        )
        if response.background is None:
            response.background = metric_task
        else:
            tasks = BackgroundTasks()
            tasks.add_task(response.background)
            tasks.add_task(metric_task)
            response.background = tasks
        return response


def _persist_request_metric(
    session_factory,  # type: ignore[no-untyped-def]
    request_id: str,
    user_id: str | None,
    endpoint: str,
    method: str,
    status_code: int,
    duration_ms: int,
    origin: str,
) -> None:
    try:
        with session_factory() as session:
            error_code = f"HTTP_{status_code}" if status_code >= 400 else None
            session.add(
                RequestMetricRecord(
                    request_id=request_id,
                    user_id=user_id,
                    endpoint=endpoint,
                    method=method,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    origin=origin,
                    error_code=error_code,
                )
            )
            if status_code >= 400:
                session.add(
                    ApplicationErrorRecord(
                        request_id=request_id,
                        user_id=user_id,
                        endpoint=endpoint,
                        code=error_code,
                    )
                )
            session.commit()
    except Exception:
        logger.exception("request_metric_persist_failed request_id=%s", request_id)
