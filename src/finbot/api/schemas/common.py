from datetime import UTC, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: str
    details: list[object] = Field(default_factory=list)


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T | None = None
    message: str | None = None
    error: ErrorDetail | None = None
    request_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int
    pages: int
