"""Failed-login rate limiter implementations.

Both the Redis-backed implementation and the in-memory test fake must honour
the same LoginRateLimiter contract: a per-identity failure counter that starts
at zero, increments on each ``hit``, expires after a fixed window, and is
cleared on ``reset`` (a successful login).
"""

import pytest

from app.infra.redis.rate_limiter import RedisLoginRateLimiter
from tests.conftest import FakeLoginRateLimiter

# ---------------------------------------------------------------------------
# FakeLoginRateLimiter — the contract every test depends on
# ---------------------------------------------------------------------------


class TestFakeLoginRateLimiter:
    async def test_fresh_identity_has_zero_count(self):
        limiter = FakeLoginRateLimiter()
        assert await limiter.count("a@example.com") == 0

    async def test_hit_increments_and_returns_running_count(self):
        limiter = FakeLoginRateLimiter()
        assert await limiter.hit("a@example.com") == 1
        assert await limiter.hit("a@example.com") == 2
        assert await limiter.count("a@example.com") == 2

    async def test_reset_clears_the_counter(self):
        limiter = FakeLoginRateLimiter()
        await limiter.hit("a@example.com")
        await limiter.reset("a@example.com")
        assert await limiter.count("a@example.com") == 0

    async def test_identities_are_independent(self):
        limiter = FakeLoginRateLimiter()
        await limiter.hit("a@example.com")
        assert await limiter.count("b@example.com") == 0


# ---------------------------------------------------------------------------
# RedisLoginRateLimiter — verified against a minimal async Redis stub
# ---------------------------------------------------------------------------


class _RedisStub:
    """Records INCR/EXPIRE/GET/DELETE — just enough surface for the wrapper."""

    def __init__(self) -> None:
        self.store: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    def incr(self, key: str) -> int:
        self.store[key] = self.store.get(key, 0) + 1
        return self.store[key]

    def expire(self, key: str, ttl: int) -> None:
        self.ttls[key] = ttl

    def get(self, key: str) -> str | None:
        value = self.store.get(key)
        return str(value) if value is not None else None

    def delete(self, key: str) -> None:
        self.store.pop(key, None)
        self.ttls.pop(key, None)


class TestRedisLoginRateLimiter:
    def setup_method(self):
        self.redis = _RedisStub()
        self.limiter = RedisLoginRateLimiter(self.redis, window_seconds=900)

    async def test_hit_increments_and_returns_count(self):
        assert await self.limiter.hit("a@example.com") == 1
        assert await self.limiter.hit("a@example.com") == 2

    async def test_count_reads_current_value(self):
        await self.limiter.hit("a@example.com")
        await self.limiter.hit("a@example.com")
        assert await self.limiter.count("a@example.com") == 2

    async def test_fresh_identity_has_zero_count(self):
        assert await self.limiter.count("a@example.com") == 0

    async def test_reset_clears_the_counter(self):
        await self.limiter.hit("a@example.com")
        await self.limiter.reset("a@example.com")
        assert await self.limiter.count("a@example.com") == 0

    async def test_keys_are_namespaced(self):
        """Counter entries must not collide with other Redis keys."""
        await self.limiter.hit("a@example.com")
        (key,) = self.redis.store
        assert key != "a@example.com"
        assert "a@example.com" in key

    async def test_window_ttl_set_once_on_first_hit(self):
        """TTL is a fixed window from the first failure, not sliding per hit."""
        await self.limiter.hit("a@example.com")
        (key,) = self.redis.ttls
        assert self.redis.ttls[key] == 900
        # a second hit must not re-arm the window
        self.redis.ttls.clear()
        await self.limiter.hit("a@example.com")
        assert self.redis.ttls == {}

    @pytest.mark.parametrize("window", [1, 60, 900])
    async def test_window_passed_verbatim(self, window):
        limiter = RedisLoginRateLimiter(self.redis, window_seconds=window)
        await limiter.hit("x@example.com")
        (ttl,) = self.redis.ttls.values()
        assert ttl == window
