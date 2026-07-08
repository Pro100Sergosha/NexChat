"""An open SSE connection must periodically re-register presence so the Redis
key's TTL is refreshed. Without this heartbeat a TTL'd presence entry would
expire mid-session and the user would wrongly look offline (notifications routed
to FCM while their tab is open). Conversely, once the tab closes the heartbeat
stops and the entry expires on its own — the leak we can't fix with `finally`
alone (dirty disconnects / server reloads never run it)."""

import asyncio

import app.infra.web.sse as sse
from app.core.notifications.repository import Presence


class CountingPresence(Presence):
    def __init__(self) -> None:
        self._online: set[tuple[str, int]] = set()
        self.register_calls = 0

    async def register(self, user_id: str, connection_id: int) -> None:
        self.register_calls += 1
        self._online.add((user_id, connection_id))

    async def unregister(self, user_id: str, connection_id: int) -> None:
        self._online.discard((user_id, connection_id))

    async def is_online(self, user_id: str) -> bool:
        return any(u == user_id for u, _ in self._online)


async def test_heartbeat_reregisters_while_streaming(fakes, monkeypatch):
    monkeypatch.setattr(sse, "PRESENCE_HEARTBEAT_SECONDS", 0.01)
    presence = CountingPresence()

    agen = sse.stream_events("user-1", presence, fakes.event_bus)
    pending = asyncio.ensure_future(agen.__anext__())
    await asyncio.sleep(0.05)  # initial register + several heartbeat refreshes

    # >1 means the heartbeat fired on top of the initial connect registration.
    assert presence.register_calls >= 2

    pending.cancel()
    await asyncio.gather(pending, return_exceptions=True)
    await agen.aclose()


async def test_heartbeat_stops_after_close(fakes, monkeypatch):
    monkeypatch.setattr(sse, "PRESENCE_HEARTBEAT_SECONDS", 0.01)
    presence = CountingPresence()

    agen = sse.stream_events("user-1", presence, fakes.event_bus)
    pending = asyncio.ensure_future(agen.__anext__())
    await asyncio.sleep(0.03)
    pending.cancel()
    await asyncio.gather(pending, return_exceptions=True)
    await agen.aclose()

    calls_after_close = presence.register_calls
    await asyncio.sleep(0.05)  # heartbeat must not keep refreshing once closed
    assert presence.register_calls == calls_after_close
    assert await presence.is_online("user-1") is False
