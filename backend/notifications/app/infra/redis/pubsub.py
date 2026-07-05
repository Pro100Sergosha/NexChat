from collections.abc import AsyncIterator
from typing import Any

from app.core.notifications.repository import EventBus

_CHANNEL_PREFIX = "notif:events:"


class RedisEventBus(EventBus):
    """Per-user fan-out over Redis pub/sub: the emit pipeline publishes to
    ``notif:events:{user_id}``; the SSE handler on whichever instance holds
    that user's socket is subscribed and streams the frame."""

    def __init__(self, client: Any) -> None:
        self._client = client

    @staticmethod
    def _channel(user_id: str) -> str:
        return f"{_CHANNEL_PREFIX}{user_id}"

    async def publish(self, user_id: str, payload: str) -> None:
        await self._client.publish(self._channel(user_id), payload)

    async def subscribe(self, user_id: str) -> AsyncIterator[str]:
        pubsub = self._client.pubsub()
        await pubsub.subscribe(self._channel(user_id))
        try:
            async for message in pubsub.listen():
                if message.get("type") == "message":
                    yield message["data"]
        finally:
            await pubsub.unsubscribe(self._channel(user_id))
            await pubsub.aclose()
