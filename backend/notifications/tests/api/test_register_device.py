"""POST /devices — register an FCM device token for the calling user."""

from tests.conftest import auth_headers, make_token


async def test_register_returns_device(client):
    ac, _db, _fakes = client
    token = make_token(sub="user-1")

    resp = await ac.post(
        "/devices",
        json={"token": "fcm-abc", "platform": "android"},
        headers=auth_headers(token),
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["token"] == "fcm-abc"
    assert body["platform"] == "android"
    assert "id" in body


async def test_register_rejects_unknown_platform(client):
    ac, _db, _fakes = client
    token = make_token(sub="user-1")

    resp = await ac.post(
        "/devices",
        json={"token": "fcm-abc", "platform": "windows-phone"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "validation_error"


async def test_register_requires_token(client):
    ac, _db, _fakes = client
    token = make_token(sub="user-1")

    resp = await ac.post(
        "/devices", json={"platform": "web"}, headers=auth_headers(token)
    )
    assert resp.status_code == 422


async def test_register_requires_auth(client):
    ac, _db, _fakes = client
    resp = await ac.post("/devices", json={"token": "x", "platform": "web"})
    assert resp.status_code == 401
