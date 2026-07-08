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


class NotificationPublisher(ABC):
    """Port for handing a new-message event off to the notifications service.

    Domain-shaped: the service asks to notify a *recipient* about a message, not
    to emit a generic broker frame — the wire/broker format is an infra concern.
    Delivery routing (SSE bell when online, FCM push when offline) is decided by
    notifications from its own presence, so chat always publishes to the
    recipient regardless of whether they hold a live chat socket here.
    """

    @abstractmethod
    async def publish_message_notification(
        self,
        *,
        recipient_id: str,
        sender_id: str,
        conversation_id: int,
        message_id: int,
        content: str,
    ) -> None: ...
