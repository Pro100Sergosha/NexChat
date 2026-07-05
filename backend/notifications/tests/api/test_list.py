"""GET /notifications — the caller's own history, newest first, never another
user's."""

from tests.conftest import auth_headers, make_notification, make_token


async def test_list_returns_own_notifications(client):
    ac, db, _fakes = client
    await make_notification(db, user_id="user-1", title="a")
    await make_notification(db, user_id="user-1", title="b")

    headers = auth_headers(make_token(sub="user-1"))
    resp = await ac.get("/notifications", headers=headers)

    assert resp.status_code == 200
    assert {n["title"] for n in resp.json()} == {"a", "b"}


async def test_list_excludes_other_users(client):
    ac, db, _fakes = client
    await make_notification(db, user_id="user-1", title="mine")
    await make_notification(db, user_id="user-2", title="theirs")

    headers = auth_headers(make_token(sub="user-1"))
    resp = await ac.get("/notifications", headers=headers)

    titles = {n["title"] for n in resp.json()}
    assert titles == {"mine"}


async def test_list_requires_auth(client):
    ac, _db, _fakes = client
    resp = await ac.get("/notifications")
    assert resp.status_code == 401
