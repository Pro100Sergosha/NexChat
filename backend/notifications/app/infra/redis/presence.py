from typing import Any

from app.core.notifications.repository import Presence
from app.infra.redis._util import resolve

_KEY_PREFIX = "notif:online:"


class RedisPresence(Presence):
    """SSE connection registry: which users are online and how many sockets
    they hold (multi-device). Mirrors chat's RedisConnectionManager."""

    def __init__(self, client: Any) -> None:
        self._client = client

    @staticmethod
    def _key(user_id: str) -> str:
        return f"{_KEY_PREFIX}{user_id}"

    async def register(self, user_id: str, connection_id: int) -> None:
        await resolve(self._client.sadd(self._key(user_id), str(connection_id)))

    async def unregister(self, user_id: str, connection_id: int) -> None:
        await resolve(self._client.srem(self._key(user_id), str(connection_id)))

    async def is_online(self, user_id: str) -> bool:
        members = await resolve(self._client.smembers(self._key(user_id)))
        return bool(members)
