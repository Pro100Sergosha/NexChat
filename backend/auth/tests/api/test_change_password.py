"""POST /change-password — contract:

* Bearer-protected; body ``{current_password, new_password}``.
* 200 → a fresh ``TokenPair`` (the caller stays logged in on the new session).
* Wrong current password → 401 ``invalid_credentials`` (same as a bad login).
* Changing the password is a **global logout**: every token issued before the
  change (old access AND old refresh) stops working.
* ``new_password`` obeys the same complexity rules as registration (422).
"""

from tests.conftest import assert_error, auth_headers, login_tokens


async def test_change_password_success_returns_new_pair(client):
    ac, db, _ = client
    pair = await login_tokens(ac, db, email="u@example.com", password="oldpass123")
    resp = await ac.post(
        "/change-password",
        json={"current_password": "oldpass123", "new_password": "newpass456!"},
        headers=auth_headers(pair["access_token"]),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"


async def test_new_pair_works_old_access_is_revoked(client):
    ac, db, _ = client
    pair = await login_tokens(ac, db, email="u@example.com", password="oldpass123")
    new = await ac.post(
        "/change-password",
        json={"current_password": "oldpass123", "new_password": "newpass456!"},
        headers=auth_headers(pair["access_token"]),
    )
    new_pair = new.json()

    # the pre-change access token no longer resolves a session
    old = await ac.get("/me", headers=auth_headers(pair["access_token"]))
    assert_error(old, 401, "token_revoked")
    # the freshly issued one does
    ok = await ac.get("/me", headers=auth_headers(new_pair["access_token"]))
    assert ok.status_code == 200


async def test_old_refresh_is_revoked_after_change(client):
    ac, db, _ = client
    pair = await login_tokens(ac, db, email="u@example.com", password="oldpass123")
    await ac.post(
        "/change-password",
        json={"current_password": "oldpass123", "new_password": "newpass456!"},
        headers=auth_headers(pair["access_token"]),
    )
    resp = await ac.post("/refresh", json={"refresh_token": pair["refresh_token"]})
    assert_error(resp, 401, "token_revoked")


async def test_wrong_current_password_unauthorized(client):
    ac, db, _ = client
    pair = await login_tokens(ac, db, email="u@example.com", password="oldpass123")
    resp = await ac.post(
        "/change-password",
        json={"current_password": "not-my-password", "new_password": "newpass456!"},
        headers=auth_headers(pair["access_token"]),
    )
    assert_error(resp, 401, "invalid_credentials")


async def test_weak_new_password_rejected(client):
    ac, db, _ = client
    pair = await login_tokens(ac, db, email="u@example.com", password="oldpass123")
    resp = await ac.post(
        "/change-password",
        json={"current_password": "oldpass123", "new_password": "short"},
        headers=auth_headers(pair["access_token"]),
    )
    assert_error(resp, 422, "validation_error")
    assert "password" in resp.json()["message"].lower()


async def test_change_password_requires_auth(client):
    ac, _, _ = client
    resp = await ac.post(
        "/change-password",
        json={"current_password": "oldpass123", "new_password": "newpass456!"},
    )
    assert_error(resp, 401, "not_authenticated")
