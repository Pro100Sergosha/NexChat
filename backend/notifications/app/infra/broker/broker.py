import logging
from collections.abc import Awaitable, Callable

import aio_pika

from app.core.config import Settings
from app.core.notifications.repository import NotificationBroker
from app.core.notifications.schemas import NotificationEvent
from app.infra.broker.config import BINDING_KEY, EXCHANGE, QUEUE, ROUTING_KEY

logger = logging.getLogger(__name__)

_EXCHANGE = EXCHANGE
_QUEUE = QUEUE
_ROUTING_KEY = ROUTING_KEY
_BINDING_KEY = BINDING_KEY


class RabbitMQBroker(NotificationBroker):
    """Durable topic exchange + queue over RabbitMQ (aio-pika).

    Producers publish persistent messages to ``nexchat.notifications``; the
    service drains the durable ``notifications.emit`` queue. A dropped consumer
    leaves messages buffered, and competing consumers load-balance the queue.
    """

    def __init__(self, settings: Settings) -> None:
        self._url = settings.RABBITMQ_URL

    async def publish(self, event: NotificationEvent) -> None:
        # Secondary/manual path — a fresh connection per publish keeps it simple.
        # TODO: pool the connection if this path ever gets hot.
        connection = await aio_pika.connect_robust(self._url)
        try:
            channel = await connection.channel()
            exchange = await channel.declare_exchange(
                _EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True
            )
            message = aio_pika.Message(
                body=event.model_dump_json().encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
            )
            await exchange.publish(message, routing_key=_ROUTING_KEY)
        finally:
            await connection.close()

    async def run_consumer(
        self, handler: Callable[[NotificationEvent], Awaitable[None]]
    ) -> None:
        connection = await aio_pika.connect_robust(self._url)
        try:
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=10)
            exchange = await channel.declare_exchange(
                _EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True
            )
            queue = await channel.declare_queue(_QUEUE, durable=True)
            await queue.bind(exchange, routing_key=_BINDING_KEY)

            logger.info("consumer started queue=%s", _QUEUE)
            async with queue.iterator() as messages:
                async for message in messages:
                    try:
                        event = NotificationEvent.model_validate_json(message.body)
                        await handler(event)
                        await message.ack()
                    except Exception:
                        logger.error(
                            "event processing failed, message dropped", exc_info=True
                        )
                        await message.nack(requeue=False)
        finally:
            await connection.close()
