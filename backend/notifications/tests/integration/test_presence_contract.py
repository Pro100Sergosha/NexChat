"""Pin RedisPresence key namespacing + set semantics against a minimal Redis
stub (mirrors auth's fake-vs-real blacklist contract test). Guards the
`notif:online:{user_id}` layout the SSE handler and emit pipeline both rely on."""

from app.infra.redis.presence import RedisPresence


class StubRedis:
    """Sync in-memory stand-in — resolve() passes non-coroutines through."""

    def __init__(self) -> None:
        self.store: dict[str, set[str]] = {}

    def sadd(self, key: str, value: str) -> None:
        self.store.setdefault(key, set()).add(value)

    def srem(self, key: str, value: str) -> None:
        self.store.get(key, set()).discard(value)

    def smembers(self, key: str) -> set[str]:
        return set(self.store.get(key, set()))


async def test_register_uses_namespaced_key():
    stub = StubRedis()
    presence = RedisPresence(stub)

    await presence.register("user-1", 5)

    assert stub.store == {"notif:online:user-1": {"5"}}


async def test_is_online_reflects_membership():
    stub = StubRedis()
    presence = RedisPresence(stub)

    assert await presence.is_online("user-1") is False
    await presence.register("user-1", 5)
    assert await presence.is_online("user-1") is True
    await presence.unregister("user-1", 5)
    assert await presence.is_online("user-1") is False


async def test_multi_device_keeps_online_until_last_leaves():
    stub = StubRedis()
    presence = RedisPresence(stub)

    await presence.register("user-1", 1)
    await presence.register("user-1", 2)
    await presence.unregister("user-1", 1)

    assert await presence.is_online("user-1") is True
