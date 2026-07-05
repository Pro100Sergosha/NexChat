"""User lookup — resolve an id or username to a public {id, username} pair.

* ``GET /users/{id}`` and ``GET /users/by-username/{username}``, Bearer-only.
* Returns only ``{id, username}`` — never email or password material.
* Unknown target → 404 ``user_not_found``.
"""

from uuid import uuid4

from tests.conftest import assert_error, auth_headers, login_tokens, make_user


async def test_lookup_by_id_returns_public_pair(client):
    ac, db, _ = client
    target, _ = await make_user(db, email="bob@example.com", username="bob")
    pair = await login_tokens(ac, db, email="caller@example.com")

    resp = await ac.get(
        f"/users/{target.id}", headers=auth_headers(pair["access_token"])
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"id": str(target.id), "username": "bob"}


async def test_lookup_by_username_returns_public_pair(client):
    ac, db, _ = client
    target, _ = await make_user(db, email="bob@example.com", username="bob")
    pair = await login_tokens(ac, db, email="caller@example.com")

    resp = await ac.get(
        "/users/by-username/bob", headers=auth_headers(pair["access_token"])
    )
    assert resp.status_code == 200
    assert resp.json() == {"id": str(target.id), "username": "bob"}


async def test_lookup_never_leaks_email(client):
    ac, db, _ = client
    target, _ = await make_user(db, email="bob@example.com", username="bob")
    pair = await login_tokens(ac, db, email="caller@example.com")

    resp = await ac.get(
        f"/users/{target.id}", headers=auth_headers(pair["access_token"])
    )
    body = resp.json()
    assert "email" not in body
    assert "hashed_password" not in body


async def test_lookup_unknown_id_not_found(client):
    ac, db, _ = client
    pair = await login_tokens(ac, db, email="caller@example.com")
    resp = await ac.get(f"/users/{uuid4()}", headers=auth_headers(pair["access_token"]))
    assert_error(resp, 404, "user_not_found")


async def test_lookup_unknown_username_not_found(client):
    ac, db, _ = client
    pair = await login_tokens(ac, db, email="caller@example.com")
    resp = await ac.get(
        "/users/by-username/ghost", headers=auth_headers(pair["access_token"])
    )
    assert_error(resp, 404, "user_not_found")


async def test_lookup_requires_auth(client):
    ac, db, _ = client
    target, _ = await make_user(db, email="bob@example.com", username="bob")
    resp = await ac.get(f"/users/{target.id}")
    assert_error(resp, 401, "not_authenticated")
