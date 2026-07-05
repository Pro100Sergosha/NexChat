"""DELETE /devices/{token} — remove own device token; never another user's."""

from tests.conftest import assert_error, auth_headers, make_device, make_token


async def test_unregister_removes_own_token(client):
    ac, db, _fakes = client
    await make_device(db, user_id="user-1", token="mine")
    token = make_token(sub="user-1")

    resp = await ac.delete("/devices/mine", headers=auth_headers(token))
    assert resp.status_code == 204

    # second delete now 404 — it's gone
    again = await ac.delete("/devices/mine", headers=auth_headers(token))
    assert_error(again, 404, "device_token_not_found")


async def test_unregister_missing_is_404(client):
    ac, _db, _fakes = client
    resp = await ac.delete(
        "/devices/nope", headers=auth_headers(make_token(sub="user-1"))
    )
    assert_error(resp, 404, "device_token_not_found")


async def test_unregister_other_owner_is_403(client):
    ac, db, _fakes = client
    await make_device(db, user_id="user-2", token="owned-by-b")

    resp = await ac.delete(
        "/devices/owned-by-b", headers=auth_headers(make_token(sub="user-1"))
    )
    assert_error(resp, 403, "not_authorized")


async def test_unregister_requires_auth(client):
    ac, db, _fakes = client
    await make_device(db, user_id="user-1", token="mine")
    resp = await ac.delete("/devices/mine")
    assert resp.status_code == 401
