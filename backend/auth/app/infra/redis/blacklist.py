from inspect import isawaitable
from typing import Any

from redis.asyncio import Redis

from app.core.auth.repository import TokenBlacklistRepository

_KEY_PREFIX = "blacklist:"


async def _resolve(value: Any) -> Any:
    """Await the result if the client returned a coroutine (real async Redis),
    otherwise pass it through as-is (sync test stubs)."""
    return await value if isawaitable(value) else value


class RedisTokenBlacklist(TokenBlacklistRepository):
    def __init__(self, client: Redis) -> None:
        self._client = client

    async def revoke(self, jti: str, ttl_seconds: int) -> None:
        await _resolve(self._client.set(f"{_KEY_PREFIX}{jti}", "1", ex=ttl_seconds))

    async def is_revoked(self, jti: str) -> bool:
        result = await _resolve(self._client.exists(f"{_KEY_PREFIX}{jti}"))
        return result > 0
