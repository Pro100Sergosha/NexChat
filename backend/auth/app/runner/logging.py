"""Logging setup: JSON-to-stdout formatter, root config, request-context middleware.

Promtail ships each container stdout line to Loki verbatim, so logs are emitted
as one JSON object per line — Grafana parses fields with LogQL ``| json``. A
per-request ``request_id`` (from an inbound ``X-Request-ID`` header or minted)
rides a contextvar so every log line within a request correlates.
"""

import json
import logging
import time
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from logging.config import dictConfig
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    """Render a LogRecord as a single-line JSON object for Loki ingestion.

    Only the stable fields are emitted (``timestamp/level/logger/message``);
    ``request_id`` is attached from the contextvar when present and ``exc_info``
    is folded into a string so the whole record stays one JSON line.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = request_id_var.get()
        if request_id is not None:
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str) -> None:
    """Point the root logger (and uvicorn's) at a JSON stdout handler.

    Idempotent — safe to call on every ``create_app()``. ``disable_existing_loggers``
    stays False so module loggers created at import time keep emitting.
    """
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"json": {"()": f"{__name__}.JsonFormatter"}},
            "handlers": {
                "stdout": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": "json",
                }
            },
            "root": {"level": level, "handlers": ["stdout"]},
            "loggers": {
                name: {"level": level, "handlers": ["stdout"], "propagate": False}
                for name in ("uvicorn", "uvicorn.access", "uvicorn.error")
            },
        }
    )


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind a request_id for the call's duration and log one access line per request."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "request id=%s method=%s path=%s status=%s dur_ms=%.1f",
                request_id,
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_var.reset(token)
