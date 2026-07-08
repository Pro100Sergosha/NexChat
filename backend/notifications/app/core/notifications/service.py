import logging
from uuid import UUID

from app.core.notifications.exceptions import (
    DeviceTokenNotFound,
    NotAuthorized,
    NotificationNotFound,
)
from app.core.notifications.model import DeviceToken, Notification
from app.core.notifications.repository import (
    DeviceTokenRepository,
    EmailSender,
    EventBus,
    NotificationRepository,
    Presence,
    PushSender,
)
from app.core.notifications.schemas import NotificationEvent, NotificationResponse

logger = logging.getLogger(__name__)


class NotificationService:
    """Emit pipeline + device-token and history management.

    ``emit`` is the single delivery path: the RabbitMQ consumer runs it per
    message, and the manual POST endpoint reaches it by publishing to the same
    broker. It never talks to the broker itself — enqueuing is the caller's job.
    """

    def __init__(
        self,
        *,
        notifications: NotificationRepository,
        device_tokens: DeviceTokenRepository,
        presence: Presence,
        event_bus: EventBus,
        push: PushSender,
        email: EmailSender,
    ) -> None:
        self._notifications = notifications
        self._device_tokens = device_tokens
        self._presence = presence
        self._event_bus = event_bus
        self._push = push
        self._email = email

    async def emit(self, event: NotificationEvent) -> Notification:
        """Persist a notification and route it to the user.

        Online users get a live event-bus publish; offline users fall back to
        FCM. Email is orthogonal to presence — a forced address on the event
        (e.g. registration verification) is delivered whether or not the user
        holds a live SSE socket.
        """
        notification = await self._notifications.create(
            user_id=event.user_id,
            type=event.type,
            title=event.title,
            body=event.body,
            data=event.data,
        )
        online = await self._presence.is_online(event.user_id)
        if online:
            payload = NotificationResponse.model_validate(
                notification
            ).model_dump_json()
            await self._event_bus.publish(event.user_id, payload)
        else:
            await self._push_offline(event.user_id, notification)
        if event.email:
            await self._email.send(event.email, notification)
        logger.info(
            "notification emitted user=%s type=%s online=%s emailed=%s",
            event.user_id,
            event.type,
            online,
            bool(event.email),
        )
        return notification

    async def _push_offline(self, user_id: str, notification: Notification) -> None:
        tokens = await self._device_tokens.list_for_user(user_id)
        if not tokens:
            return
        invalid = await self._push.send(tokens, notification)
        if invalid:
            await self._device_tokens.delete_many(invalid)

    async def list_for_user(self, user_id: str) -> list[Notification]:
        return await self._notifications.list_for_user(user_id)

    async def mark_read(self, user_id: str, notification_id: UUID) -> None:
        notification = await self._notifications.get_by_id(notification_id)
        if notification is None:
            raise NotificationNotFound()
        if notification.user_id != user_id:
            raise NotAuthorized()
        await self._notifications.mark_read(notification_id)

    async def register_device(
        self, *, user_id: str, token: str, platform: str
    ) -> DeviceToken:
        existing = await self._device_tokens.get_by_token(token)
        if existing is not None and existing.user_id == user_id:
            return existing
        return await self._device_tokens.add(
            user_id=user_id, token=token, platform=platform
        )

    async def unregister_device(self, *, user_id: str, token: str) -> None:
        existing = await self._device_tokens.get_by_token(token)
        if existing is None:
            raise DeviceTokenNotFound()
        if existing.user_id != user_id:
            raise NotAuthorized()
        await self._device_tokens.remove(token)
