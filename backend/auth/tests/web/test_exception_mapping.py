"""Error contract — the single source of truth for every error the API emits.

Every ``AppException`` maps to:
  * a stable HTTP status,
  * a machine-readable snake_case ``code`` (frontend branches on it),
  * a human-readable English ``message`` (frontend can show it as-is).

Pydantic validation failures (422) are rewritten into the same shape with
friendly, per-case messages — never the raw pydantic error list.
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, EmailStr, Field

from app.core.exception import AppException
from app.infra.web.responses import register_exception_handlers
from tests.conftest import assert_error

# ---------------------------------------------------------------------------
# the catalog — spec for every domain error
# ---------------------------------------------------------------------------

ERROR_CATALOG = [
    # (exception class name, http status, code, exact message)
    ("UserAlreadyExists", 409, "user_already_exists", "A user with this email already exists"),
    ("InvalidCredentials", 401, "invalid_credentials", "Email or password is incorrect"),
    ("UserNotFound", 404, "user_not_found", "User not found"),
    ("TokenInvalid", 401, "token_invalid", "The token is invalid"),
    ("TokenExpired", 401, "token_expired", "The token has expired"),
    ("TokenRevoked", 401, "token_revoked", "The token has been revoked"),
    ("NotAuthenticated", 401, "not_authenticated", "Authentication credentials were not provided"),
]


def _load_exception(name: str) -> type[AppException]:
    import app.core.auth.exceptions as exceptions_module

    cls = getattr(exceptions_module, name, None)
    assert cls is not None, f"exception {name} must exist in core/auth/exceptions.py"
    return cls


class _Payload(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


def _make_app() -> FastAPI:
    """Minimal app exercising the exception handlers in isolation."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom/{name}")
    async def boom(name: str) -> None:
        raise _load_exception(name)()

    @app.post("/validated")
    async def validated(payload: _Payload) -> dict:
        return {"ok": True}

    return app


@pytest.fixture
async def raw_client():
    transport = ASGITransport(app=_make_app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# domain exceptions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "status", "code", "message"), ERROR_CATALOG)
async def test_domain_exception_maps_to_contract(raw_client, name, status, code, message):
    resp = await raw_client.get(f"/boom/{name}")
    assert_error(resp, status, code)
    assert resp.json()["message"] == message


@pytest.mark.parametrize(("name", "_status", "code", "message"), ERROR_CATALOG)
async def test_exception_class_carries_code_and_message(name, _status, code, message):
    """The code/message pair lives on the exception itself, usable outside HTTP."""
    exc = _load_exception(name)()
    assert exc.code == code
    assert exc.message == message


async def test_unknown_app_exception_falls_back_to_400(raw_client):
    class Unmapped(AppException):
        code = "unmapped"
        message = "Something domain-specific went wrong"

    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        raise Unmapped()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/boom")
    assert_error(resp, 400, "unmapped")


# ---------------------------------------------------------------------------
# validation errors — friendly 422s
# ---------------------------------------------------------------------------


async def test_validation_short_password_mentions_minimum(raw_client):
    resp = await raw_client.post(
        "/validated", json={"email": "a@b.com", "password": "short"}
    )
    assert_error(resp, 422, "validation_error")
    message = resp.json()["message"].lower()
    assert "password" in message
    assert "8" in message


async def test_validation_bad_email_mentions_email(raw_client):
    resp = await raw_client.post(
        "/validated", json={"email": "nope", "password": "password123"}
    )
    assert_error(resp, 422, "validation_error")
    assert "email" in resp.json()["message"].lower()


async def test_validation_missing_field_names_it(raw_client):
    resp = await raw_client.post("/validated", json={"password": "password123"})
    assert_error(resp, 422, "validation_error")
    assert "email" in resp.json()["message"].lower()


async def test_validation_response_has_no_raw_pydantic_shape(raw_client):
    """No `detail` list with loc/msg/type dicts — only {code, message}."""
    resp = await raw_client.post("/validated", json={})
    body = resp.json()
    assert "detail" not in body
    assert set(body) == {"code", "message"}
