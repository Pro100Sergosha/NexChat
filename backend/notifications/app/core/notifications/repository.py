from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any
from uuid import UUID

from app.core.notifications.model import DeviceToken, Notification
from app.core.notifications.schemas import NotificationEvent


class NotificationRepository(ABC):
    @abstractmethod
    async def create(
        self,
        *,
        user_id: str,
        type: str,
        title: str,
        body: str,
        data: dict[str, Any],
    ) -> Notification: ...

    @abstractmethod
    async def get_by_id(self, notification_id: UUID) -> Notification | None: ...

    @abstractmethod
    async def list_for_user(self, user_id: str) -> list[Notification]: ...

    @abstractmethod
    async def mark_read(self, notification_id: UUID) -> None: ...


class DeviceTokenRepository(ABC):
    @abstractmethod
    async def add(self, *, user_id: str, token: str, platform: str) -> DeviceToken: ...

    @abstractmethod
    async def get_by_token(self, token: str) -> DeviceToken | None: ...

    @abstractmethod
    async def list_for_user(self, user_id: str) -> list[DeviceToken]: ...

    @abstractmethod
    async def remove(self, token: str) -> None: ...

    @abstractmethod
    async def delete_many(self, tokens: set[str]) -> None: ...


class Presence(ABC):
    """Which users currently hold a live SSE connection, across instances.

    Mirrors chat's ConnectionManager (Redis set per user, multi-device)."""

    @abstractmethod
    async def register(self, user_id: str, connection_id: int) -> None: ...

    @abstractmethod
    async def unregister(self, user_id: str, connection_id: int) -> None: ...

    @abstractmethod
    async def is_online(self, user_id: str) -> bool: ...


class EventBus(ABC):
    """Per-user fan-out from the emit pipeline to whichever instance holds the
    user's SSE socket. Ephemeral (Redis pub/sub) — not the durable broker."""

    @abstractmethod
    async def publish(self, user_id: str, payload: str) -> None: ...

    @abstractmethod
    def subscribe(self, user_id: str) -> AsyncIterator[str]: ...


class NotificationBroker(ABC):
    """Durable producer→service message broker (RabbitMQ). Decouples emitters
    (chat, admin) from the notifications pipeline."""

    @abstractmethod
    async def publish(self, event: NotificationEvent) -> None: ...

    @abstractmethod
    async def run_consumer(
        self, handler: Callable[[NotificationEvent], Awaitable[None]]
    ) -> None: ...


class PushSender(ABC):
    """Offline delivery via FCM. ``send`` returns the tokens FCM reports as
    unregistered so the caller can prune them."""

    @abstractmethod
    async def send(
        self, tokens: list[DeviceToken], notification: Notification
    ) -> set[str]: ...


class EmailSender(ABC):
    """Email delivery channel. Sends one notification to a concrete address.

    Used for forced/transactional email (e.g. registration verification), where
    the recipient address rides the event rather than device registration — so
    the channel is orthogonal to SSE/FCM presence routing."""

    @abstractmethod
    async def send(self, address: str, notification: Notification) -> None: ...
