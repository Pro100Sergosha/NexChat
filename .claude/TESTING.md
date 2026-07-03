# Testing Conventions

Applies to every backend service (`auth`, `chat`, ...). TDD: tests are written
first as the spec, implementation follows until the suite is green. Don't
edit tests to make implementation easier — fix the implementation.

## Test pyramid layout

```
tests/
  conftest.py       # shared fixtures + factories (see below)
  unit/             # core/*.py in isolation — mocked repos, no I/O
  integration/       # infra/*.py against real-ish backends (sqlite, fakes)
  web/              # infra/web/dependables.py, exception→HTTP mapping
  api/              # one file per endpoint, full stack via ASGITransport
  ws/               # WebSocket services only — one file per concern
                     # (handshake, message flow, disconnect), full stack
                     # via a sync TestClient (ASGITransport has no WS support)
```

One test file per endpoint under `api/` (`test_register.py`, `test_login.py`,
...) — not one monolithic `test_<service>.py`. Each file documents its
endpoint's contract in a module docstring. Services with a WebSocket layer
(chat) follow the same one-file-per-concern rule under `ws/` instead of
`api/`, since a WS connection isn't a single request/response endpoint.

WS auth/validation failures have no HTTP status or JSON body, so they use
custom close codes instead of the `{code, message}` contract — pin the
catalog in the `ws/` module docstrings (chat: 4401 auth, 4403 not
participant, 4422 bad payload). A handshake rejection closes before
`.accept()`, so entering the client's `websocket_connect(...)` context
itself raises `WebSocketDisconnect` — assert on `.code` there rather than
after a successful connect.

## Test infra

- DB: `sqlite+aiosqlite:///:memory:` via SQLAlchemy async engine + `StaticPool`
  — no testcontainers, no real Postgres.
- Redis: in-memory fake implementing the repository's `ABC` interface
  (e.g. `FakeBlacklist`), not a mocked client. Also keep a fake-vs-real
  contract test in `integration/` (see `test_blacklist.py` in auth) that pins
  key namespacing and TTL semantics against a minimal Redis stub.
- Never mock the DB session in integration tests — use the real sqlite engine
  so unique constraints, cascades, etc. are actually exercised.

## Error contract — every service, every error

All domain exceptions inherit `AppException` and carry:

```python
class SomeError(AppException):
    code = "some_error"          # stable snake_case, frontend branches on this
    message = "Human-readable English sentence."
```

The shared exception handler renders `{"code": ..., "message": ...}` — never
`{"detail": "ClassName"}`, never a bare HTTP status with no body. Pydantic
`RequestValidationError` (422) is rewritten into the same shape with a
message that names the offending field and constraint (e.g. "Password must
be at least 8 characters"), never the raw pydantic error list.

Pin the full catalog in one place per service:
`tests/web/test_exception_mapping.py`, table-driven over
`(exception_name, http_status, code, message)`.

## Required test helper: `assert_error`

Every service's `conftest.py` should expose this (copy from auth, adjust
imports):

```python
def assert_error(resp, status: int, code: str) -> None:
    assert resp.status_code == status
    body = resp.json()
    assert body.get("code") == code
    message = body.get("message")
    assert isinstance(message, str) and message.strip()
    assert message != code
    assert " " in message  # must be prose, not a slug
```

Use it for every non-2xx assertion instead of hand-rolled status/body checks.

## Other required conftest helpers

- `make_user(db, *, email, password)` — insert a user with a real password
  hash, return `(User, plaintext_password)`.
- `make_token(*, sub, token_type, expires_in, jti, secret)` — craft a JWT
  directly (bypassing the service) to control every claim, including
  already-expired tokens and wrong-signature forgeries.
- `auth_headers(token)` → `{"Authorization": f"Bearer {token}"}`.
- `login_tokens(ac, db, *, email, password)` — create a user and log in
  through the real API, return the token pair dict. Don't duplicate this
  per test file.
- `InMemoryUserRepository` — dict-backed `UserRepository` for unit-level
  dependency tests that need a real (not mocked) repo without a DB session.

## Outcome coverage checklist (per endpoint)

- Happy path, asserting the full response shape.
- Every distinct failure cause gets its OWN test and its OWN `code` — don't
  collapse "wrong password" and "unknown user" into one assertion, but DO
  assert they return the identical body (no user enumeration).
- 422 validation: missing field, wrong type, out-of-range, empty body — each
  asserts the message names the field.
- Auth-protected routes: missing header, wrong scheme, garbage token, wrong
  token type (e.g. refresh used as access), expired token, revoked token,
  token for a since-deleted subject — each is a separate test with its own
  expected `code`.
- Ownership / authorization (IDOR): for any route scoped to a resource owned
  by a specific user, a second authenticated user must NOT be able to
  read/modify/delete it via another user's id — assert a deliberate status
  (403 or 404, pick one per service and stay consistent), never silent
  success and never a leaked 500. This is orthogonal to authentication above:
  the token is valid, the *subject* just isn't the resource's owner. Test
  both directions (A acting on B's resource and vice versa) since ownership
  checks are often asymmetric bugs.
