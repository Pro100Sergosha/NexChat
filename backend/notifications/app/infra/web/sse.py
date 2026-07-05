from collections.abc import AsyncIterator

from fastapi import Request
from fastapi.responses import Response

from app.core.config import settings
from app.core.notifications.repository import EventBus, Presence
from app.core.notifications.security import TokenVerifier


async def stream_events(
    user_id: str, presence: Presence, event_bus: EventBus
) -> AsyncIterator[str]:
    """The SSE body: register presence, relay each per-user event as it is
    published, and always unregister on close (client disconnect or shutdown).

    Extracted from the endpoint so it can be driven directly in tests without
    standing up a streaming HTTP client."""
    sentinel = object()  # keep alive so its id stays a stable connection key
    connection_id = id(sentinel)
    await presence.register(user_id, connection_id)
    try:
        async for payload in event_bus.subscribe(user_id):
            yield payload
    finally:
        await presence.unregister(user_id, connection_id)


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
