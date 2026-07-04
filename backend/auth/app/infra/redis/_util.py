from inspect import isawaitable
from typing import Any


async def resolve(value: Any) -> Any:
    """Await the result if the client returned a coroutine (real async Redis),
    otherwise pass it through as-is (sync test stubs)."""
    return await value if isawaitable(value) else value
