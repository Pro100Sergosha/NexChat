from abc import ABC, abstractmethod

from app.core.chat.model import Conversation, Message


class ConversationRepository(ABC):
    @abstractmethod
    async def create(self, user_a_id: str, user_b_id: str) -> Conversation: ...

    @abstractmethod
    async def get_by_id(self, conversation_id: int) -> Conversation | None: ...

    @abstractmethod
    async def get_by_pair(
        self, user_a_id: str, user_b_id: str
    ) -> Conversation | None: ...

    @abstractmethod
    async def list_for_user(self, user_id: str) -> list[Conversation]: ...

    @abstractmethod
    async def delete(self, conversation_id: int) -> None: ...


class MessageRepository(ABC):
    @abstractmethod
    async def create(
        self, *, conversation_id: int, sender_id: str, content: str
    ) -> Message: ...

    @abstractmethod
    async def list_for_conversation(
        self, *, conversation_id: int, limit: int, offset: int
    ) -> list[Message]: ...
