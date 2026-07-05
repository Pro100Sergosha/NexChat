"""POST /verify-email — contract:

* Body ``{"token": <verify-jwt>}``; 204 No Content on success.
* Confirms the account: a previously unverified user can then log in.
* The link is single-use — replaying a spent token returns 409
  ``email_already_verified`` (same as confirming an already-verified account).
* Bad/expired/wrong-type/forged tokens follow {"code", "message"}:
  ``token_invalid`` / ``token_expired`` (401).
"""

from tests.conftest import assert_error, make_token, make_user


async def _verify_token_for(db, *, email: str, email_verified: bool = False) -> str:
    user, _ = await make_user(db, email=email, email_verified=email_verified)
    return make_token(sub=str(user.id), token_type="verify")


# ---------------------------------------------------------------------------
# success
# ---------------------------------------------------------------------------


async def test_verify_success_returns_204(client):
    ac, db, _ = client
    token = await _verify_token_for(db, email="v@example.com")
    resp = await ac.post("/verify-email", json={"token": token})
    assert resp.status_code == 204


async def test_verify_then_login_succeeds(client):
    ac, db, _ = client
    user, password = await make_user(db, email="v@example.com", email_verified=False)
    token = make_token(sub=str(user.id), token_type="verify")

    # unverified → login blocked
    blocked = await ac.post(
        "/login", data={"username": "v@example.com", "password": password}
    )
    assert_error(blocked, 403, "email_not_verified")

    await ac.post("/verify-email", json={"token": token})

    ok = await ac.post(
        "/login", data={"username": "v@example.com", "password": password}
    )
    assert ok.status_code == 200


# ---------------------------------------------------------------------------
# single-use / idempotency
# ---------------------------------------------------------------------------


async def test_reused_token_conflicts(client):
    ac, db, _ = client
    token = await _verify_token_for(db, email="v@example.com")
    first = await ac.post("/verify-email", json={"token": token})
    assert first.status_code == 204
    second = await ac.post("/verify-email", json={"token": token})
    assert_error(second, 409, "email_already_verified")


async def test_already_verified_user_conflicts(client):
    ac, db, _ = client
    token = await _verify_token_for(db, email="v@example.com", email_verified=True)
    resp = await ac.post("/verify-email", json={"token": token})
    assert_error(resp, 409, "email_already_verified")


# ---------------------------------------------------------------------------
# bad tokens
# ---------------------------------------------------------------------------


async def test_garbage_token_rejected(client):
    ac, _, _ = client
    resp = await ac.post("/verify-email", json={"token": "not-a-jwt"})
    assert_error(resp, 401, "token_invalid")


async def test_wrong_type_token_rejected(client):
    ac, db, _ = client
    user, _ = await make_user(db, email="v@example.com", email_verified=False)
    access = make_token(sub=str(user.id), token_type="access")
    resp = await ac.post("/verify-email", json={"token": access})
    assert_error(resp, 401, "token_invalid")


async def test_expired_token_rejected(client):
    ac, db, _ = client
    user, _ = await make_user(db, email="v@example.com", email_verified=False)
    expired = make_token(sub=str(user.id), token_type="verify", expires_in=-60)
    resp = await ac.post("/verify-email", json={"token": expired})
    assert_error(resp, 401, "token_expired")


async def test_forged_signature_rejected(client):
    ac, db, _ = client
    user, _ = await make_user(db, email="v@example.com", email_verified=False)
    forged = make_token(sub=str(user.id), token_type="verify", secret="attacker-secret")
    resp = await ac.post("/verify-email", json={"token": forged})
    assert_error(resp, 401, "token_invalid")


async def test_missing_token_field_rejected(client):
    ac, _, _ = client
    resp = await ac.post("/verify-email", json={})
    assert_error(resp, 422, "validation_error")
