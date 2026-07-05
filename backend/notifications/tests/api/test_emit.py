"""POST /notifications — producer-facing enqueue onto the broker.

Authorized by X-Service-Token (a trusted-producer secret), NOT a user JWT: the
recipient is an arbitrary user_id, so a user Bearer would let anyone spoof
notifications to any user (IDOR). Contract: 202 Accepted, published once, and —
because the fake broker drives the pipeline — persisted to the recipient's
history."""

from tests.conftest import auth_headers, make_token, service_headers

BODY = {
    "user_id": "user-1",
    "type": "message",
    "title": "New message",
    "body": "hello there",
    "data": {"conversation_id": "7"},
}


async def test_emit_accepts_and_publishes(client):
    ac, _db, fakes = client

    resp = await ac.post("/notifications", json=BODY, headers=service_headers())

    assert resp.status_code == 202
    assert len(fakes.broker.published) == 1
    assert fakes.broker.published[0].user_id == "user-1"


async def test_emit_persists_to_history(client):
    ac, _db, _fakes = client

    await ac.post("/notifications", json=BODY, headers=service_headers())

    # the recipient reads their own history with a user token
    listed = await ac.get(
        "/notifications", headers=auth_headers(make_token(sub="user-1"))
    )
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) == 1
    assert items[0]["title"] == "New message"
    assert items[0]["read"] is False


async def test_emit_with_email_delivers_over_email_channel(client):
    ac, _db, fakes = client
    body = {**BODY, "email": "user@example.com"}

    resp = await ac.post("/notifications", json=body, headers=service_headers())

    assert resp.status_code == 202
    assert fakes.broker.published[0].email == "user@example.com"
    assert len(fakes.email.sent) == 1
    assert fakes.email.sent[0][0] == "user@example.com"


async def test_emit_without_service_token_is_403(client):
    ac, _db, fakes = client

    resp = await ac.post("/notifications", json=BODY)

    assert resp.status_code == 403
    assert resp.json()["code"] == "not_authorized"
    assert fakes.broker.published == []


async def test_emit_rejects_user_jwt(client):
    ac, _db, _fakes = client

    # A valid user token must NOT authorize emit — this is the IDOR guard.
    resp = await ac.post(
        "/notifications", json=BODY, headers=auth_headers(make_token(sub="attacker"))
    )

    assert resp.status_code == 403


async def test_emit_wrong_service_token_is_403(client):
    ac, _db, _fakes = client

    resp = await ac.post(
        "/notifications", json=BODY, headers={"X-Service-Token": "wrong"}
    )

    assert resp.status_code == 403


async def test_emit_validates_body(client):
    ac, _db, _fakes = client
    bad = {"user_id": "user-1", "title": "x", "body": "y"}  # missing type

    resp = await ac.post("/notifications", json=bad, headers=service_headers())

    assert resp.status_code == 422
    assert resp.json()["code"] == "validation_error"
