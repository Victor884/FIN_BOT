from pydantic import BaseModel, ConfigDict, Field


class TelegramChat(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    type: str


class TelegramUser(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    is_bot: bool = False
    first_name: str | None = None
    username: str | None = None


class TelegramMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message_id: int
    date: int
    chat: TelegramChat
    from_user: TelegramUser | None = Field(default=None, alias="from")
    text: str | None = None


class TelegramUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    update_id: int
    message: TelegramMessage | None = None
