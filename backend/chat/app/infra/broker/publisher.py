import json
import logging

import aio_pika

from app.core.chat.repository import NotificationPublisher
from app.infra.broker.config import EXCHANGE, ROUTING_KEY

logger = logging.getLogger(__name__)

_TYPE = "chat.message"
_TITLE = "New message"
# chat has no usernames (only UUIDs), so the title is stable and the sender is
# carried in `data` for the client to resolve against auth's /users lookup.
_BODY_MAX = 200


class RabbitMQPublisher(NotificationPublisher):
    """Publishes ``NotificationEvent``-shaped messages to the notifications broker.

    chat never imports the notifications package (separate service, separate DB),
    so the event dict is built by hand against the documented wire contract:
    ``user_id / type / title / body / data / email``. No forced ``email`` — chat
    events route by presence (SSE/FCM), not the transactional email channel.

    Unlike auth (low-volume, fresh connection per publish), chat publishes on
    every message, so the connection + channel + exchange are opened once at
    startup (``connect``) and reused. Until connected — or if the broker was down
    at startup — ``publish_*`` is a silent no-op so message delivery never breaks.
    """

    def __init__(self, url: str) -> None:
        self._url = url
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._exchange: aio_pika.abc.AbstractExchange | None = None

    async def connect(self) -> None:
        self._connection = await aio_pika.connect_robust(self._url)
        channel = await self._connection.channel()
        self._exchange = await channel.declare_exchange(
            EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True
        )

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()

    async def publish_message_notification(
        self,
        *,
        recipient_id: str,
        sender_id: str,
        conversation_id: int,
        message_id: int,
        content: str,
    ) -> None:
        if self._exchange is None:
            # Broker unavailable at startup — best-effort, drop the notification.
            return
        event = {
            "user_id": recipient_id,
            "type": _TYPE,
            "title": _TITLE,
            "body": content[:_BODY_MAX],
            "data": {
                "conversation_id": str(conversation_id),
                "message_id": str(message_id),
                "sender_id": sender_id,
            },
            "email": None,
        }
        message = aio_pika.Message(
            body=json.dumps(event).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
        )
        await self._exchange.publish(message, routing_key=ROUTING_KEY)
