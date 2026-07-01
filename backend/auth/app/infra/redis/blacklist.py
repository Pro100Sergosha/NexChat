from redis.asyncio import Redis

from app.core.auth.repository import TokenBlacklistRepository

_KEY_PREFIX = "blacklist:"


class RedisTokenBlacklist(TokenBlacklistRepository):
    def __init__(self, client: Redis) -> None:
        self._client = client

    async def revoke(self, jti: str, ttl_seconds: int) -> None:
        await self._client.set(f"{_KEY_PREFIX}{jti}", "1", ex=ttl_seconds)

    async def is_revoked(self, jti: str) -> bool:
        return await self._client.exists(f"{_KEY_PREFIX}{jti}") > 0
