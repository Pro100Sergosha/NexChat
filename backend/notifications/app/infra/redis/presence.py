from typing import Any

from app.core.notifications.repository import Presence
from app.infra.redis._util import resolve

_KEY_PREFIX = "notif:online:"

# Presence self-heals: without a heartbeat refresh (see sse.stream_events) an
# entry outlives its connection by at most this long. A crashed/reloaded server
# — where the SSE `finally` never ran unregister — therefore can't pin a user
# "online" forever and misroute their notifications to a dead socket instead of
# FCM. Must stay comfortably above the heartbeat interval or a live connection
# would flicker offline between refreshes.
_TTL_SECONDS = 30


class RedisPresence(Presence):
    """SSE connection registry: which users are online and how many sockets
    they hold (multi-device). Mirrors chat's RedisConnectionManager."""

    def __init__(self, client: Any) -> None:
        self._client = client

    @staticmethod
    def _key(user_id: str) -> str:
        return f"{_KEY_PREFIX}{user_id}"

    async def register(self, user_id: str, connection_id: int) -> None:
        key = self._key(user_id)
        await resolve(self._client.sadd(key, str(connection_id)))
        # (Re)arm the TTL on every register — the SSE heartbeat re-registers to
        # keep an active user online; the key expires once refreshes stop.
        await resolve(self._client.expire(key, _TTL_SECONDS))

    async def unregister(self, user_id: str, connection_id: int) -> None:
        await resolve(self._client.srem(self._key(user_id), str(connection_id)))

    async def is_online(self, user_id: str) -> bool:
        members = await resolve(self._client.smembers(self._key(user_id)))
        return bool(members)
