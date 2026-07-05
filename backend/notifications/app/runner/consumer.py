from app.core.config import settings
from app.core.notifications.schemas import NotificationEvent
from app.core.notifications.service import NotificationService
from app.infra.broker.broker import RabbitMQBroker
from app.infra.database.config import async_session_factory
from app.infra.database.repositories import (
    SqlAlchemyDeviceTokenRepository,
    SqlAlchemyNotificationRepository,
)
from app.infra.fcm.client import FirebasePushSender
from app.infra.redis.config import redis_client
from app.infra.redis.presence import RedisPresence
from app.infra.redis.pubsub import RedisEventBus


async def process_event(event: NotificationEvent) -> None:
    """Run the emit pipeline for one consumed message. Each event gets its own
    DB session so a slow/failed event can't poison others."""
    async with async_session_factory() as session:
        service = NotificationService(
            notifications=SqlAlchemyNotificationRepository(session),
            device_tokens=SqlAlchemyDeviceTokenRepository(session),
            presence=RedisPresence(redis_client),
            event_bus=RedisEventBus(redis_client),
            push=FirebasePushSender(settings),
        )
        await service.emit(event)


async def run_consumer() -> None:
    broker = RabbitMQBroker(settings)
    await broker.run_consumer(process_event)
