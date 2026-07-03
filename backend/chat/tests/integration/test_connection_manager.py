"""Active WebSocket connection registry.

Both the Redis-backed implementation and the in-memory test fake must honour
the same ConnectionManager contract; the fake is what tests/ws/* relies on,
so its behaviour is pinned here too. Tracks *connection ids* per user (not
just a boolean) to support multi-device: a user can have several live
sockets and removing one must not mark them offline.
"""

from app.infra.redis.connection_manager import RedisConnectionManager
from tests.conftest import FakeConnectionManager

# ---------------------------------------------------------------------------
# FakeConnectionManager — the contract every WS test depends on
# ---------------------------------------------------------------------------


class TestFakeConnectionManager:
    async def test_unregistered_user_is_offline(self):
        manager = FakeConnectionManager()
        assert await manager.is_online("user-a") is False

    async def test_register_marks_online(self):
        manager = FakeConnectionManager()
        await manager.register("user-a", 1)
        assert await manager.is_online("user-a") is True

    async def test_unregister_last_connection_marks_offline(self):
        manager = FakeConnectionManager()
        await manager.register("user-a", 1)
        await manager.unregister("user-a", 1)
        assert await manager.is_online("user-a") is False

    async def test_multi_device_connections_all_tracked(self):
        manager = FakeConnectionManager()
        await manager.register("user-a", 1)
        await manager.register("user-a", 2)
        assert await manager.connections_for("user-a") == {1, 2}

    async def test_unregister_one_device_keeps_others_online(self):
        manager = FakeConnectionManager()
        await manager.register("user-a", 1)
        await manager.register("user-a", 2)
        await manager.unregister("user-a", 1)
        assert await manager.is_online("user-a") is True
        assert await manager.connections_for("user-a") == {2}

    async def test_users_are_independent(self):
        manager = FakeConnectionManager()
        await manager.register("user-a", 1)
        assert await manager.is_online("user-b") is False


# ---------------------------------------------------------------------------
# RedisConnectionManager — verified against a minimal async Redis stub
# ---------------------------------------------------------------------------


class _RedisStub:
    """Records SADD/SREM calls and answers SMEMBERS — enough surface for
    the wrapper's set-per-user model."""

    def __init__(self) -> None:
        self.store: dict[str, set[str]] = {}

    def sadd(self, key: str, member: str) -> None:
        self.store.setdefault(key, set()).add(member)

    def srem(self, key: str, member: str) -> None:
        self.store.get(key, set()).discard(member)

    def smembers(self, key: str) -> set[str]:
        return set(self.store.get(key, set()))


class TestRedisConnectionManager:
    def setup_method(self):
        self.redis = _RedisStub()
        self.manager = RedisConnectionManager(self.redis)

    async def test_register_then_is_online(self):
        await self.manager.register("user-a", 1)
        assert await self.manager.is_online("user-a") is True

    async def test_fresh_user_is_offline(self):
        assert await self.manager.is_online("user-a") is False

    async def test_keys_are_namespaced(self):
        """Connection entries must not collide with other Redis keys."""
        await self.manager.register("user-a", 1)
        (key,) = self.redis.store
        assert key != "user-a"
        assert "user-a" in key

    async def test_multi_device_tracked_in_same_set(self):
        await self.manager.register("user-a", 1)
        await self.manager.register("user-a", 2)
        assert await self.manager.connections_for("user-a") == {1, 2}

    async def test_unregister_removes_only_that_connection(self):
        await self.manager.register("user-a", 1)
        await self.manager.register("user-a", 2)
        await self.manager.unregister("user-a", 1)
        assert await self.manager.connections_for("user-a") == {2}
        assert await self.manager.is_online("user-a") is True

    async def test_unregister_last_connection_marks_offline(self):
        await self.manager.register("user-a", 1)
        await self.manager.unregister("user-a", 1)
        assert await self.manager.is_online("user-a") is False
