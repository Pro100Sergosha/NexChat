from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.config import settings


class ConversationOut(BaseModel):
    id: int
    other_user_id: str
    created_at: datetime
    last_message_at: datetime | None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    sender_id: str
    content: str
    created_at: datetime


class WSSendMessage(BaseModel):
    content: str = Field(min_length=1, max_length=settings.MESSAGE_MAX_LENGTH)
    recipient_id: str | None = None
    conversation_id: int | None = None

    @model_validator(mode="after")
    def _requires_a_target(self) -> "WSSendMessage":
        if self.recipient_id is None and self.conversation_id is None:
            raise ValueError("recipient_id or conversation_id is required")
        return self
