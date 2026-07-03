"""POST /logout — contract:

* Requires a Bearer access token in Authorization AND the refresh token in
  the body; revokes BOTH.
* 204 No Content on success.
* Errors follow {"code", "message"}.
"""

from tests.conftest import assert_error, auth_headers, login_tokens, make_token

# ---------------------------------------------------------------------------
# success
# ---------------------------------------------------------------------------


async def test_logout_success_returns_204(client):
    ac, db, _ = client
    tokens = await login_tokens(ac, db)
    resp = await ac.post(
        "/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers=auth_headers(tokens["access_token"]),
    )
    assert resp.status_code == 204
    assert resp.content == b""


async def test_logout_revokes_refresh_token(client):
    ac, db, _ = client
    tokens = await login_tokens(ac, db)
    await ac.post(
        "/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers=auth_headers(tokens["access_token"]),
    )
    resp = await ac.post("/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert_error(resp, 401, "token_revoked")


async def test_logout_revokes_access_token(client):
    """After logout the access token must stop working on protected routes."""
    ac, db, _ = client
    tokens = await login_tokens(ac, db)
    await ac.post(
        "/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers=auth_headers(tokens["access_token"]),
    )
    resp = await ac.get("/me", headers=auth_headers(tokens["access_token"]))
    assert_error(resp, 401, "token_revoked")


# ---------------------------------------------------------------------------
# authentication failures
# ---------------------------------------------------------------------------


async def test_logout_without_bearer_unauthorized(client):
    ac, db, _ = client
    tokens = await login_tokens(ac, db)
    resp = await ac.post("/logout", json={"refresh_token": tokens["refresh_token"]})
    assert_error(resp, 401, "not_authenticated")


async def test_logout_with_garbage_access_token_rejected(client):
    ac, db, _ = client
    tokens = await login_tokens(ac, db)
    resp = await ac.post(
        "/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers=auth_headers("not-a-jwt"),
    )
    assert_error(resp, 401, "token_invalid")


async def test_logout_with_swapped_tokens_rejected(client):
    """Access token in the body / refresh token in the header — type mismatch."""
    ac, db, _ = client
    tokens = await login_tokens(ac, db)
    resp = await ac.post(
        "/logout",
        json={"refresh_token": tokens["access_token"]},
        headers=auth_headers(tokens["refresh_token"]),
    )
    assert_error(resp, 401, "token_invalid")


async def test_logout_with_expired_access_token_rejected(client):
    ac, db, _ = client
    tokens = await login_tokens(ac, db)
    expired = make_token(expires_in=-60)
    resp = await ac.post(
        "/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers=auth_headers(expired),
    )
    assert_error(resp, 401, "token_expired")


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------


async def test_logout_missing_refresh_token_rejected(client):
    ac, db, _ = client
    tokens = await login_tokens(ac, db)
    resp = await ac.post(
        "/logout", json={}, headers=auth_headers(tokens["access_token"])
    )
    assert_error(resp, 422, "validation_error")
