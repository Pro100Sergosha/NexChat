import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress

from fastapi import Request
from fastapi.responses import Response

from app.core.config import settings
from app.core.notifications.repository import EventBus, Presence
from app.core.notifications.security import TokenVerifier

# Re-register presence this often to keep its Redis TTL armed while the socket
# is open. Must stay well under RedisPresence._TTL_SECONDS so a live connection
# never flickers offline; once the socket closes the refreshes stop and the
# entry expires on its own (covers dirty disconnects where `finally` never ran).
PRESENCE_HEARTBEAT_SECONDS = 10


async def stream_events(
    user_id: str, presence: Presence, event_bus: EventBus
) -> AsyncIterator[str]:
    """The SSE body: register presence, relay each per-user event as it is
    published, and always unregister on close (client disconnect or shutdown).

    A background heartbeat re-registers on an interval so presence has a TTL we
    can rely on: unregister in `finally` is best-effort (a killed/reloaded
    worker never runs it), so the TTL is what actually clears a dead socket.

    Extracted from the endpoint so it can be driven directly in tests without
    standing up a streaming HTTP client."""
    sentinel = object()  # keep alive so its id stays a stable connection key
    connection_id = id(sentinel)
    await presence.register(user_id, connection_id)
    heartbeat = asyncio.create_task(
        _refresh_presence(user_id, connection_id, presence)
    )
    try:
        async for payload in event_bus.subscribe(user_id):
            yield payload
    finally:
        heartbeat.cancel()
        with suppress(asyncio.CancelledError):
            await heartbeat
        await presence.unregister(user_id, connection_id)


async def _refresh_presence(
    user_id: str, connection_id: int, presence: Presence
) -> None:
    while True:
        await asyncio.sleep(PRESENCE_HEARTBEAT_SECONDS)
        await presence.register(user_id, connection_id)


async def events_endpoint(
    request: Request,
    presence: Presence,
    event_bus: EventBus,
    verifier: TokenVerifier,
) -> Response:
    # EventSource can't set headers, so the access token rides the query string
    # (same reason chat's WS does). A bad token raises TokenInvalid/TokenExpired
    # → 401 before any streaming starts.
    token = request.query_params.get("token") or ""
    user_id = verifier.verify_access_token(token)

    # Lazy import: sse-starlette is only needed to actually serve the stream.
    from sse_starlette.sse import EventSourceResponse

    return EventSourceResponse(
        stream_events(user_id, presence, event_bus),
        ping=settings.sse_keepalive_seconds,
    )
