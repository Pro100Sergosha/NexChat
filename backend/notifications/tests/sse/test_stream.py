"""The SSE body generator relays published events and marks the user online.

Driven directly (not through a streaming HTTP client) so the assertion is
deterministic — same code path the endpoint wraps in EventSourceResponse."""

import asyncio

from app.infra.web.sse import stream_events


async def test_stream_yields_published_event(fakes):
    agen = stream_events("user-1", fakes.presence, fakes.event_bus)
    pending = asyncio.ensure_future(agen.__anext__())
    await asyncio.sleep(0.02)  # let it register + subscribe

    assert await fakes.presence.is_online("user-1") is True

    await fakes.event_bus.publish("user-1", '{"id": "abc"}')
    received = await asyncio.wait_for(pending, timeout=1)

    assert received == '{"id": "abc"}'
    await agen.aclose()


async def test_stream_registers_only_its_own_user(fakes):
    agen = stream_events("user-1", fakes.presence, fakes.event_bus)
    pending = asyncio.ensure_future(agen.__anext__())
    await asyncio.sleep(0.02)

    assert await fakes.presence.is_online("user-1") is True
    assert await fakes.presence.is_online("user-2") is False

    pending.cancel()
    await asyncio.gather(pending, return_exceptions=True)
    await agen.aclose()
