import json
from typing import Any

import aio_pika

from app.core.auth.repository import NotificationPublisher
from app.core.config import Settings
from app.infra.broker.config import EXCHANGE, ROUTING_KEY

# Fixed wire fields per transactional email. The notifications service routes on
# the forced `email` (transactional channel), so `type`/`title` are for its
# history/display only.
_VERIFY_TYPE = "email_verification"
_VERIFY_TITLE = "Verify your email"
_RESET_TYPE = "password_reset"
_RESET_TITLE = "Reset your password"


class RabbitMQPublisher(NotificationPublisher):
    """Publishes ``NotificationEvent``-shaped messages to the notifications broker.

    auth never imports the notifications package (separate service, separate DB),
    so the event dict is built by hand against the documented wire contract:
    ``user_id / type / title / body / data / email``. A forced ``email`` tells the
    consumer to deliver over SMTP regardless of the recipient's presence.
    """

    def __init__(self, settings: Settings) -> None:
        self._url = settings.RABBITMQ_URL

    async def publish_verification(
        self, *, user_id: str, email: str, verify_url: str
    ) -> None:
        await self._publish(
            {
                "user_id": user_id,
                "type": _VERIFY_TYPE,
                "title": _VERIFY_TITLE,
                "body": f"Confirm your email address: {verify_url}",
                "data": {"verify_url": verify_url},
                "email": email,
            }
        )

    async def publish_password_reset(
        self, *, user_id: str, email: str, reset_url: str
    ) -> None:
        await self._publish(
            {
                "user_id": user_id,
                "type": _RESET_TYPE,
                "title": _RESET_TITLE,
                "body": f"Reset your password: {reset_url}",
                "data": {"reset_url": reset_url},
                "email": email,
            }
        )

    async def _publish(self, event: dict[str, Any]) -> None:
        # Fresh connection per publish — this path is low-volume (registration /
        # manual resend / password reset); pool it only if it ever gets hot.
        connection = await aio_pika.connect_robust(self._url)
        try:
            channel = await connection.channel()
            exchange = await channel.declare_exchange(
                EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True
            )
            message = aio_pika.Message(
                body=json.dumps(event).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
            )
            await exchange.publish(message, routing_key=ROUTING_KEY)
        finally:
            await connection.close()
