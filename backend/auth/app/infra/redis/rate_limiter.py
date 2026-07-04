from redis.asyncio import Redis

from app.core.auth.repository import LoginRateLimiter
from app.infra.redis._util import resolve

_KEY_PREFIX = "login_attempts:"

# How long the failed-login counter lives before it resets (15 minutes).
WINDOW_SECONDS = 900


class RedisLoginRateLimiter(LoginRateLimiter):
    def __init__(self, client: Redis, window_seconds: int = WINDOW_SECONDS) -> None:
        self._client = client
        self._window = window_seconds

    async def hit(self, identity: str) -> int:
        key = f"{_KEY_PREFIX}{identity}"
        count = await resolve(self._client.incr(key))
        # Fixed window, not sliding: arm the TTL only on the first failure so the
        # lockout can't be extended indefinitely by hammering the endpoint.
        if count == 1:
            await resolve(self._client.expire(key, self._window))
        return count

    async def count(self, identity: str) -> int:
        value = await resolve(self._client.get(f"{_KEY_PREFIX}{identity}"))
        return int(value) if value is not None else 0

    async def reset(self, identity: str) -> None:
        await resolve(self._client.delete(f"{_KEY_PREFIX}{identity}"))
