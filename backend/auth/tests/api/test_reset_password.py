"""POST /reset-password — contract:

* Body ``{token, new_password}``; 204 on success.
* ``token`` is a single-use ``type=reset`` JWT (from the forgot-password email).
* After a reset the old password no longer works and every session issued
  before it is revoked (global logout via password_changed_at).
* Reused link → 409 ``token_revoked``; bad/expired/wrong-type → 401.
"""

from tests.conftest import assert_error, auth_headers, make_token, make_user


async def test_reset_sets_new_password(client):
    ac, db, _ = client
    user, _ = await make_user(db, email="u@example.com", password="oldpass123")
    token = make_token(sub=str(user.id), token_type="reset")

    resp = await ac.post(
        "/reset-password", json={"token": token, "new_password": "newpass456!"}
    )
    assert resp.status_code == 204

    # old password rejected, new one works
    old = await ac.post(
        "/login", data={"username": "u@example.com", "password": "oldpass123"}
    )
    assert_error(old, 401, "invalid_credentials")
    new = await ac.post(
        "/login", data={"username": "u@example.com", "password": "newpass456!"}
    )
    assert new.status_code == 200


async def test_reset_revokes_pre_existing_sessions(client):
    ac, db, _ = client
    user, _ = await make_user(db, email="u@example.com", password="oldpass123")
    # a session minted before the reset (iat in the past via make_token)
    stale_access = make_token(sub=str(user.id), token_type="access")
    token = make_token(sub=str(user.id), token_type="reset")

    await ac.post(
        "/reset-password", json={"token": token, "new_password": "newpass456!"}
    )
    resp = await ac.get("/me", headers=auth_headers(stale_access))
    assert_error(resp, 401, "token_revoked")


async def test_reused_reset_token_conflicts(client):
    ac, db, _ = client
    user, _ = await make_user(db, email="u@example.com", password="oldpass123")
    token = make_token(sub=str(user.id), token_type="reset")

    first = await ac.post(
        "/reset-password", json={"token": token, "new_password": "newpass456!"}
    )
    assert first.status_code == 204
    second = await ac.post(
        "/reset-password", json={"token": token, "new_password": "another789!"}
    )
    assert_error(second, 401, "token_revoked")


async def test_wrong_type_token_rejected(client):
    ac, db, _ = client
    user, _ = await make_user(db, email="u@example.com")
    access = make_token(sub=str(user.id), token_type="access")
    resp = await ac.post(
        "/reset-password", json={"token": access, "new_password": "newpass456!"}
    )
    assert_error(resp, 401, "token_invalid")


async def test_expired_token_rejected(client):
    ac, db, _ = client
    user, _ = await make_user(db, email="u@example.com")
    expired = make_token(sub=str(user.id), token_type="reset", expires_in=-60)
    resp = await ac.post(
        "/reset-password", json={"token": expired, "new_password": "newpass456!"}
    )
    assert_error(resp, 401, "token_expired")


async def test_garbage_token_rejected(client):
    ac, _, _ = client
    resp = await ac.post(
        "/reset-password", json={"token": "not-a-jwt", "new_password": "newpass456!"}
    )
    assert_error(resp, 401, "token_invalid")


async def test_weak_new_password_rejected(client):
    ac, db, _ = client
    user, _ = await make_user(db, email="u@example.com")
    token = make_token(sub=str(user.id), token_type="reset")
    resp = await ac.post(
        "/reset-password", json={"token": token, "new_password": "short"}
    )
    assert_error(resp, 422, "validation_error")
    assert "password" in resp.json()["message"].lower()
