"""POST /refresh — contract:

* Body: {"refresh_token": "<jwt>"} → 200 with a NEW TokenPair.
* Rotation: the presented refresh token is revoked; replaying it → 401.
* Only refresh-type tokens are accepted; each failure has its own code:
  token_invalid / token_expired / token_revoked.
"""

from tests.conftest import assert_error, login_tokens, make_token

# ---------------------------------------------------------------------------
# success + rotation
# ---------------------------------------------------------------------------


async def test_refresh_success_returns_new_pair(client):
    ac, db, _ = client
    tokens = await login_tokens(ac, db)
    resp = await ac.post("/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"


async def test_refresh_issues_different_tokens(client):
    """Rotation must mint a fresh pair, not echo the old tokens back."""
    ac, db, _ = client
    tokens = await login_tokens(ac, db)
    resp = await ac.post("/refresh", json={"refresh_token": tokens["refresh_token"]})
    body = resp.json()
    assert body["refresh_token"] != tokens["refresh_token"]
    assert body["access_token"] != tokens["access_token"]


async def test_refresh_rotation_revokes_old_token(client):
    ac, db, _ = client
    tokens = await login_tokens(ac, db)
    first = await ac.post("/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert first.status_code == 200
    # replay of the already-rotated refresh token must fail
    replay = await ac.post("/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert_error(replay, 401, "token_revoked")


async def test_refresh_rotated_token_stays_usable(client):
    """The pair returned by /refresh must itself be refreshable (chain works)."""
    ac, db, _ = client
    tokens = await login_tokens(ac, db)
    first = await ac.post("/refresh", json={"refresh_token": tokens["refresh_token"]})
    second = await ac.post(
        "/refresh", json={"refresh_token": first.json()["refresh_token"]}
    )
    assert second.status_code == 200


# ---------------------------------------------------------------------------
# wrong token kind / bad tokens — each cause gets a distinct code
# ---------------------------------------------------------------------------


async def test_refresh_with_access_token_rejected(client):
    ac, db, _ = client
    tokens = await login_tokens(ac, db)
    resp = await ac.post("/refresh", json={"refresh_token": tokens["access_token"]})
    assert_error(resp, 401, "token_invalid")


async def test_refresh_garbage_token_rejected(client):
    ac, _, _ = client
    resp = await ac.post("/refresh", json={"refresh_token": "not-a-jwt"})
    assert_error(resp, 401, "token_invalid")


async def test_refresh_wrong_signature_rejected(client):
    ac, _, _ = client
    forged = make_token(token_type="refresh", secret="attacker-secret")
    resp = await ac.post("/refresh", json={"refresh_token": forged})
    assert_error(resp, 401, "token_invalid")


async def test_refresh_expired_token_rejected(client):
    ac, _, _ = client
    expired = make_token(token_type="refresh", expires_in=-60)
    resp = await ac.post("/refresh", json={"refresh_token": expired})
    assert_error(resp, 401, "token_expired")


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------


async def test_refresh_missing_field_rejected(client):
    ac, _, _ = client
    resp = await ac.post("/refresh", json={})
    assert_error(resp, 422, "validation_error")
