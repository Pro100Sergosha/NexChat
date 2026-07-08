"""SSE connection lifecycle is logged: one ``sse connected`` on register and one
``sse disconnected`` on close, both with the user id.

Drives ``stream_events`` directly (same as tests/sse/test_stream.py) rather than
standing up a streaming HTTP client."""

import asyncio
import logging

from app.infra.web.sse import stream_events

_SSE_LOGGER = "app.infra.web.sse"


async def test_connect_and_disconnect_are_logged(fakes, caplog):
    with caplog.at_level(logging.INFO, logger=_SSE_LOGGER):
        agen = stream_events("user-1", fakes.presence, fakes.event_bus)
        pending = asyncio.ensure_future(agen.__anext__())
        await asyncio.sleep(0.02)  # let it register + subscribe
        pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)
        await agen.aclose()

    msgs = [r.getMessage() for r in caplog.records if r.name == _SSE_LOGGER]
    assert any("sse connected" in m and "user-1" in m for m in msgs)
    assert any("sse disconnected" in m and "user-1" in m for m in msgs)
