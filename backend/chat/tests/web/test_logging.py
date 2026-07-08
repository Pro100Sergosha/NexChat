"""Structured logging — contract:

* ``JsonFormatter`` renders each record as a single JSON line carrying
  ``timestamp / level / logger / message``; ``%``-args are rendered into
  ``message``; ``exc_info`` is serialised as a string; ``request_id`` appears
  only when the contextvar is set.
* ``RequestContextMiddleware`` logs exactly one ``request`` line per HTTP call
  (method / path / status / duration) and echoes/mints an ``X-Request-ID``.
"""

import json
import logging
import sys

from app.runner.logging import JsonFormatter, request_id_var


def _record(
    msg: str, args=None, *, level=logging.INFO, exc_info=None
) -> logging.LogRecord:
    return logging.LogRecord("app.sample", level, "sample.py", 10, msg, args, exc_info)


# ── JsonFormatter ─────────────────────────────────────────────────────────────


def test_formatter_emits_json_with_core_fields():
    out = json.loads(JsonFormatter().format(_record("hello world")))
    assert out["level"] == "INFO"
    assert out["logger"] == "app.sample"
    assert out["message"] == "hello world"
    assert "timestamp" in out


def test_formatter_renders_percent_args():
    out = json.loads(JsonFormatter().format(_record("user=%s", ("u1",))))
    assert out["message"] == "user=u1"


def test_formatter_omits_request_id_when_unset():
    out = json.loads(JsonFormatter().format(_record("hi")))
    assert "request_id" not in out


def test_formatter_includes_request_id_when_set():
    token = request_id_var.set("abc123")
    try:
        out = json.loads(JsonFormatter().format(_record("hi")))
        assert out["request_id"] == "abc123"
    finally:
        request_id_var.reset(token)


def test_formatter_serialises_exc_info_as_string():
    try:
        raise ValueError("boom")
    except ValueError:
        out = json.loads(
            JsonFormatter().format(
                _record("failed", level=logging.ERROR, exc_info=sys.exc_info())
            )
        )
    assert isinstance(out["exc_info"], str)
    assert "boom" in out["exc_info"]


# ── RequestContextMiddleware ──────────────────────────────────────────────────


async def test_request_is_logged_once_with_status(client, caplog):
    with caplog.at_level(logging.INFO, logger="app.runner.logging"):
        resp = await client.get("/health")
    assert resp.status_code == 200
    lines = [
        r.getMessage()
        for r in caplog.records
        if r.name == "app.runner.logging" and "request" in r.getMessage()
    ]
    assert len(lines) == 1
    assert "status=200" in lines[0]
    assert "path=/health" in lines[0]


async def test_response_carries_request_id_header(client):
    resp = await client.get("/health")
    assert resp.headers.get("x-request-id")


async def test_inbound_request_id_is_echoed(client):
    resp = await client.get("/health", headers={"X-Request-ID": "req-42"})
    assert resp.headers.get("x-request-id") == "req-42"
