"""POST /notifications/{id}/read — mark own notification read; never another's."""

from uuid import uuid4

from tests.conftest import assert_error, auth_headers, make_notification, make_token


async def test_mark_read_sets_flag(client):
    ac, db, _fakes = client
    notification = await make_notification(db, user_id="user-1")
    token = make_token(sub="user-1")

    resp = await ac.post(
        f"/notifications/{notification.id}/read", headers=auth_headers(token)
    )
    assert resp.status_code == 204

    listed = await ac.get("/notifications", headers=auth_headers(token))
    assert listed.json()[0]["read"] is True


async def test_mark_read_missing_is_404(client):
    ac, _db, _fakes = client
    resp = await ac.post(
        f"/notifications/{uuid4()}/read", headers=auth_headers(make_token(sub="user-1"))
    )
    assert_error(resp, 404, "notification_not_found")


async def test_mark_read_other_owner_is_403(client):
    ac, db, _fakes = client
    notification = await make_notification(db, user_id="user-1")

    resp = await ac.post(
        f"/notifications/{notification.id}/read",
        headers=auth_headers(make_token(sub="user-2")),
    )
    assert_error(resp, 403, "not_authorized")


async def test_mark_read_requires_auth(client):
    ac, db, _fakes = client
    notification = await make_notification(db, user_id="user-1")
    resp = await ac.post(f"/notifications/{notification.id}/read")
    assert resp.status_code == 401
