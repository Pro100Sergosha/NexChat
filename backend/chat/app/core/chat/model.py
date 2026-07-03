from dataclasses import dataclass
from datetime import datetime


@dataclass
class Conversation:
    id: int
    user_a_id: str
    user_b_id: str
    created_at: datetime
    last_message_at: datetime | None

    def has_participant(self, user_id: str) -> bool:
        return user_id in (self.user_a_id, self.user_b_id)


@dataclass
class Message:
    id: int
    conversation_id: int
    sender_id: str
    content: str
    created_at: datetime
