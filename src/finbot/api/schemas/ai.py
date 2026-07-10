from pydantic import BaseModel, Field, field_validator


class AiCompletionRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)

    @field_validator("prompt")
    @classmethod
    def normalize_prompt(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("prompt must not be blank")
        return value


class AiCompletionData(BaseModel):
    text: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
