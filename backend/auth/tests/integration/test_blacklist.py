"""Token blacklist implementations.

Both the Redis-backed implementation and the in-memory test fake must honour
the same TokenBlacklistRepository contract; the fake is what every other test
relies on, so its behaviour is pinned here too.
"""

import pytest

from app.infra.redis.blacklist import RedisTokenBlacklist
from tests.conftest import FakeBlacklist

# ---------------------------------------------------------------------------
# FakeBlacklist — the contract every test depends on
# ---------------------------------------------------------------------------


class TestFakeBlacklist:
    async def test_fresh_jti_is_not_revoked(self):
        blacklist = FakeBlacklist()
        assert await blacklist.is_revoked("jti-1") is False

    async def test_revoked_jti_is_reported(self):
        blacklist = FakeBlacklist()
        await blacklist.revoke("jti-1", 3600)
        assert await blacklist.is_revoked("jti-1") is True

    async def test_jtis_are_independent(self):
        blacklist = FakeBlacklist()
        await blacklist.revoke("jti-1", 3600)
        assert await blacklist.is_revoked("jti-2") is False


# ---------------------------------------------------------------------------
# RedisTokenBlacklist — verified against a minimal async Redis stub
# ---------------------------------------------------------------------------


class _RedisStub:
    """Records SET calls and answers EXISTS — just enough surface for the wrapper."""

    def __init__(self) -> None:
        self.store: dict[str, tuple[str, int]] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = (value, ex)

    async def exists(self, key: str) -> int:
        return 1 if key in self.store else 0


class TestRedisTokenBlacklist:
    def setup_method(self):
        self.redis = _RedisStub()
        self.blacklist = RedisTokenBlacklist(self.redis)

    async def test_revoke_then_is_revoked_roundtrip(self):
        await self.blacklist.revoke("jti-1", 3600)
        assert await self.blacklist.is_revoked("jti-1") is True

    async def test_fresh_jti_is_not_revoked(self):
        assert await self.blacklist.is_revoked("jti-1") is False

    async def test_keys_are_namespaced(self):
        """Blacklist entries must not collide with other Redis keys."""
        await self.blacklist.revoke("jti-1", 3600)
        (key,) = self.redis.store
        assert key != "jti-1"  # some prefix is applied
        assert "jti-1" in key

    async def test_entry_expires_with_token_ttl(self):
        """The Redis entry must carry the token's remaining TTL, not live forever."""
        await self.blacklist.revoke("jti-1", 1234)
        (_, ttl) = next(iter(self.redis.store.values()))
        assert ttl == 1234

    @pytest.mark.parametrize("ttl", [1, 60, 604800])
    async def test_ttl_passed_verbatim(self, ttl):
        await self.blacklist.revoke("jti-x", ttl)
        (_, stored) = next(iter(self.redis.store.values()))
        assert stored == ttl
