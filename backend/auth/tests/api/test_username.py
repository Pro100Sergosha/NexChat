"""Username — registration field, uniqueness, and POST /change-username.

* ``/register`` now requires a ``username``: 3-32 chars, ``[a-z0-9_]``,
  case-insensitive-unique (stored lowercase). Clash → 409 ``username_taken``.
* ``/me`` and ``/register`` responses expose ``username``.
* ``/change-username`` (Bearer) renames the caller, guarding uniqueness.
"""

from tests.conftest import assert_error, auth_headers, login_tokens, make_user

_PW = "password123!"


async def test_register_requires_username(client):
    ac, _, _ = client
    resp = await ac.post(
        "/register", json={"email": "new@example.com", "password": _PW}
    )
    assert_error(resp, 422, "validation_error")
    assert "username" in resp.json()["message"].lower()


async def test_register_returns_username_lowercased(client):
    ac, _, _ = client
    resp = await ac.post(
        "/register",
        json={"email": "new@example.com", "username": "Alice_1", "password": _PW},
    )
    assert resp.status_code == 201
    assert resp.json()["username"] == "alice_1"


async def test_duplicate_username_conflicts_case_insensitive(client):
    ac, db, _ = client
    await make_user(db, email="a@example.com", username="alice")
    resp = await ac.post(
        "/register",
        json={"email": "b@example.com", "username": "ALICE", "password": _PW},
    )
    assert_error(resp, 409, "username_taken")


async def test_too_short_username_rejected(client):
    ac, _, _ = client
    resp = await ac.post(
        "/register",
        json={"email": "new@example.com", "username": "ab", "password": _PW},
    )
    assert_error(resp, 422, "validation_error")
    assert "username" in resp.json()["message"].lower()


async def test_illegal_chars_username_rejected(client):
    ac, _, _ = client
    resp = await ac.post(
        "/register",
        json={"email": "new@example.com", "username": "bad name!", "password": _PW},
    )
    assert_error(resp, 422, "validation_error")
    assert "username" in resp.json()["message"].lower()


async def test_me_exposes_username(client):
    ac, db, _ = client
    pair = await login_tokens(ac, db, email="u@example.com")
    resp = await ac.get("/me", headers=auth_headers(pair["access_token"]))
    assert resp.status_code == 200
    assert "username" in resp.json()


async def test_change_username_renames_caller(client):
    ac, db, _ = client
    pair = await login_tokens(ac, db, email="u@example.com")
    resp = await ac.post(
        "/change-username",
        json={"username": "renamed"},
        headers=auth_headers(pair["access_token"]),
    )
    assert resp.status_code == 200
    assert resp.json()["username"] == "renamed"

    me = await ac.get("/me", headers=auth_headers(pair["access_token"]))
    assert me.json()["username"] == "renamed"


async def test_change_username_to_taken_conflicts(client):
    ac, db, _ = client
    await make_user(db, email="other@example.com", username="taken")
    pair = await login_tokens(ac, db, email="u@example.com")
    resp = await ac.post(
        "/change-username",
        json={"username": "TAKEN"},
        headers=auth_headers(pair["access_token"]),
    )
    assert_error(resp, 409, "username_taken")


async def test_change_username_requires_auth(client):
    ac, _, _ = client
    resp = await ac.post("/change-username", json={"username": "whoever"})
    assert_error(resp, 401, "not_authenticated")
