from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("invalid email")
        return value


class RegisterRequest(LoginRequest):
    name: str = Field(min_length=2, max_length=120)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=32)


class TelegramLinkRequest(LoginRequest):
    code: str = Field(min_length=12, max_length=100)
    name: str | None = Field(default=None, min_length=2, max_length=120)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthUser(BaseModel):
    id: str
    name: str | None
    email: str | None
    role: str
