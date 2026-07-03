"""GET /me — contract:

* Protected by a Bearer access token; returns the current user {id, email}.
* Every authentication failure has its own code so the client can react
  (e.g. token_expired → try /refresh, token_revoked → force re-login).
"""

from tests.conftest import (
    assert_error,
    auth_headers,
    login_tokens,
    make_token,
    make_user,
)

# ---------------------------------------------------------------------------
# success
# ---------------------------------------------------------------------------


async def test_me_returns_current_user(client):
    ac, db, _ = client
    tokens = await login_tokens(ac, db, email="me@example.com")
    resp = await ac.get("/me", headers=auth_headers(tokens["access_token"]))
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "me@example.com"
    assert "id" in body
    assert "hashed_password" not in body


# ---------------------------------------------------------------------------
# authentication failures — one distinct code per cause
# ---------------------------------------------------------------------------


async def test_me_without_header_unauthorized(client):
    ac, _, _ = client
    resp = await ac.get("/me")
    assert_error(resp, 401, "not_authenticated")


async def test_me_with_non_bearer_scheme_unauthorized(client):
    ac, _, _ = client
    resp = await ac.get("/me", headers={"Authorization": "Basic dXNlcjpwYXNz"})
    assert_error(resp, 401, "not_authenticated")


async def test_me_with_garbage_token_rejected(client):
    ac, _, _ = client
    resp = await ac.get("/me", headers=auth_headers("not-a-jwt"))
    assert_error(resp, 401, "token_invalid")


async def test_me_with_expired_access_rejected(client):
    ac, db, _ = client
    user, _ = await make_user(db)
    expired = make_token(sub=str(user.id), expires_in=-60)
    resp = await ac.get("/me", headers=auth_headers(expired))
    assert_error(resp, 401, "token_expired")


async def test_me_with_refresh_token_rejected(client):
    """A refresh token must never grant access to protected routes."""
    ac, db, _ = client
    tokens = await login_tokens(ac, db)
    resp = await ac.get("/me", headers=auth_headers(tokens["refresh_token"]))
    assert_error(resp, 401, "token_invalid")


async def test_me_with_revoked_access_rejected(client):
    ac, db, _ = client
    tokens = await login_tokens(ac, db)
    await ac.post(
        "/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers=auth_headers(tokens["access_token"]),
    )
    resp = await ac.get("/me", headers=auth_headers(tokens["access_token"]))
    assert_error(resp, 401, "token_revoked")


async def test_me_with_token_for_deleted_user_rejected(client):
    """Valid signature but the subject no longer exists — token is useless."""
    ac, _, _ = client
    ghost = make_token(sub="00000000-0000-0000-0000-000000000000")
    resp = await ac.get("/me", headers=auth_headers(ghost))
    assert_error(resp, 401, "token_invalid")
