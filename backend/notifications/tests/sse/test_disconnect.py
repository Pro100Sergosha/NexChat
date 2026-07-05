"""On disconnect (client gone / server shutdown) the SSE body must unregister
presence in its finally block — a leaked online entry would misroute later
notifications to a dead socket instead of FCM."""

import asyncio

from app.infra.web.sse import stream_events


async def test_presence_cleared_on_cancel(fakes):
    agen = stream_events("user-1", fakes.presence, fakes.event_bus)
    pending = asyncio.ensure_future(agen.__anext__())
    await asyncio.sleep(0.02)
    assert await fakes.presence.is_online("user-1") is True

    # Simulate the disconnect: cancel the in-flight receive.
    pending.cancel()
    await asyncio.gather(pending, return_exceptions=True)

    assert await fakes.presence.is_online("user-1") is False


async def test_presence_cleared_on_aclose(fakes):
    agen = stream_events("user-1", fakes.presence, fakes.event_bus)
    pending = asyncio.ensure_future(agen.__anext__())
    await asyncio.sleep(0.02)
    await fakes.event_bus.publish("user-1", "frame")
    await asyncio.wait_for(pending, timeout=1)

    await agen.aclose()

    assert await fakes.presence.is_online("user-1") is False
