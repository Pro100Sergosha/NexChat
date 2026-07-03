from abc import ABC, abstractmethod
from inspect import isawaitable
from typing import Any

_KEY_PREFIX = "chat:online:"


async def _resolve(value: Any) -> Any:
    """Await the result if the client returned a coroutine (real async Redis),
    otherwise pass it through as-is (sync test stubs)."""
    return await value if isawaitable(value) else value


class ConnectionManager(ABC):
    """Active WebSocket connection registry: which users are online, and
    which connection ids they currently hold (multi-device support)."""

    @abstractmethod
    async def register(self, user_id: str, connection_id: int) -> None: ...

    @abstractmethod
    async def unregister(self, user_id: str, connection_id: int) -> None: ...

    @abstractmethod
    async def is_online(self, user_id: str) -> bool: ...

    @abstractmethod
    async def connections_for(self, user_id: str) -> set[int]: ...


class RedisConnectionManager(ConnectionManager):
    def __init__(self, client: Any) -> None:
        self._client = client

    @staticmethod
    def _key(user_id: str) -> str:
        return f"{_KEY_PREFIX}{user_id}"

    async def register(self, user_id: str, connection_id: int) -> None:
        await _resolve(self._client.sadd(self._key(user_id), str(connection_id)))

    async def unregister(self, user_id: str, connection_id: int) -> None:
        await _resolve(self._client.srem(self._key(user_id), str(connection_id)))

    async def is_online(self, user_id: str) -> bool:
        members = await _resolve(self._client.smembers(self._key(user_id)))
        return bool(members)

    async def connections_for(self, user_id: str) -> set[int]:
        members = await _resolve(self._client.smembers(self._key(user_id)))
        return {int(member) for member in members}
