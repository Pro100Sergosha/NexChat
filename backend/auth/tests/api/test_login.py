"""POST /login — contract:

* OAuth2 password form: ``application/x-www-form-urlencoded`` with
  ``username`` (the email) and ``password``. Standard FastAPI OAuth2 flow,
  works with the Swagger "Authorize" button.
* 200 → TokenPair {access_token, refresh_token, token_type="bearer"}.
* Unknown user and wrong password return the SAME error — the API must not
  reveal whether an email is registered.
* Errors follow {"code", "message"} with a human-readable message.
"""

from app.core.auth.service import MAX_LOGIN_ATTEMPTS
from tests.conftest import assert_error, make_user

# ---------------------------------------------------------------------------
# success
# ---------------------------------------------------------------------------


async def test_login_success_returns_token_pair(client):
    ac, db, _ = client
    _, password = await make_user(db, email="login@example.com")
    resp = await ac.post(
        "/login", data={"username": "login@example.com", "password": password}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"


async def test_login_email_is_case_insensitive(client):
    ac, db, _ = client
    _, password = await make_user(db, email="login@example.com")
    resp = await ac.post(
        "/login", data={"username": "LoGiN@Example.COM", "password": password}
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# invalid credentials — identical error for both causes
# ---------------------------------------------------------------------------


async def test_login_wrong_password_unauthorized(client):
    ac, db, _ = client
    await make_user(db, email="login@example.com", password="password123")
    resp = await ac.post(
        "/login", data={"username": "login@example.com", "password": "wrong-password"}
    )
    assert_error(resp, 401, "invalid_credentials")


async def test_login_unknown_user_unauthorized(client):
    ac, _, _ = client
    resp = await ac.post(
        "/login", data={"username": "ghost@example.com", "password": "password123"}
    )
    assert_error(resp, 401, "invalid_credentials")


async def test_login_does_not_reveal_which_field_was_wrong(client):
    """Same status, code, and message whether the email exists or not."""
    ac, db, _ = client
    await make_user(db, email="known@example.com", password="password123")
    wrong_password = await ac.post(
        "/login", data={"username": "known@example.com", "password": "bad-password"}
    )
    unknown_user = await ac.post(
        "/login", data={"username": "ghost@example.com", "password": "bad-password"}
    )
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()


# ---------------------------------------------------------------------------
# rate limiting — lockout after repeated failures (429)
# ---------------------------------------------------------------------------


async def test_login_locks_out_after_repeated_failures(client):
    ac, db, _ = client
    await make_user(db, email="lock@example.com", password="password123")
    limit = MAX_LOGIN_ATTEMPTS
    for _ in range(limit):
        bad = await ac.post(
            "/login", data={"username": "lock@example.com", "password": "wrong"}
        )
        assert_error(bad, 401, "invalid_credentials")
    locked = await ac.post(
        "/login", data={"username": "lock@example.com", "password": "wrong"}
    )
    assert_error(locked, 429, "too_many_attempts")


async def test_login_lockout_ignores_a_correct_password(client):
    """Once locked, even the right password is refused until the window clears."""
    ac, db, _ = client
    _, password = await make_user(db, email="lock@example.com")
    for _ in range(MAX_LOGIN_ATTEMPTS):
        await ac.post(
            "/login", data={"username": "lock@example.com", "password": "wrong"}
        )
    locked = await ac.post(
        "/login", data={"username": "lock@example.com", "password": password}
    )
    assert_error(locked, 429, "too_many_attempts")


async def test_login_success_clears_failure_counter(client):
    ac, db, _ = client
    _, password = await make_user(db, email="lock@example.com")
    # stay one short of the limit, then succeed
    for _ in range(MAX_LOGIN_ATTEMPTS - 1):
        await ac.post(
            "/login", data={"username": "lock@example.com", "password": "wrong"}
        )
    ok = await ac.post(
        "/login", data={"username": "lock@example.com", "password": password}
    )
    assert ok.status_code == 200
    # counter reset → the same number of failures again does NOT lock immediately
    bad = await ac.post(
        "/login", data={"username": "lock@example.com", "password": "wrong"}
    )
    assert_error(bad, 401, "invalid_credentials")


async def test_login_lockout_does_not_reveal_unknown_user(client):
    """An unknown email locks out identically — no enumeration via 429 timing."""
    ac, _, _ = client
    for _ in range(MAX_LOGIN_ATTEMPTS):
        await ac.post(
            "/login", data={"username": "ghost@example.com", "password": "wrong"}
        )
    locked = await ac.post(
        "/login", data={"username": "ghost@example.com", "password": "wrong"}
    )
    assert_error(locked, 429, "too_many_attempts")


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------


async def test_login_missing_username_rejected(client):
    ac, _, _ = client
    resp = await ac.post("/login", data={"password": "password123"})
    assert_error(resp, 422, "validation_error")


async def test_login_missing_password_rejected(client):
    ac, _, _ = client
    resp = await ac.post("/login", data={"username": "login@example.com"})
    assert_error(resp, 422, "validation_error")


async def test_login_json_body_rejected(client):
    """The contract is form-encoded OAuth2 — JSON bodies must not be accepted."""
    ac, db, _ = client
    _, password = await make_user(db, email="login@example.com")
    resp = await ac.post(
        "/login", json={"username": "login@example.com", "password": password}
    )
    assert_error(resp, 422, "validation_error")
