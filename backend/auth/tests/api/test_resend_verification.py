"""POST /resend-verification — contract:

* Body ``{"email": <address>}``; always 202 Accepted, empty body.
* Anti-enumeration: the response is identical whether the address exists, is
  already verified, or is unknown — only a real *unverified* user is actually
  re-sent a verification email.
* Per-address throttle caps how many mails a single address can trigger.
"""

from tests.conftest import make_user


async def test_resend_for_unverified_user_publishes(client, publisher):
    ac, db, _ = client
    user, _ = await make_user(db, email="u@example.com", email_verified=False)
    resp = await ac.post("/resend-verification", json={"email": "u@example.com"})
    assert resp.status_code == 202
    assert len(publisher.calls) == 1
    assert publisher.calls[0]["user_id"] == str(user.id)


async def test_resend_for_verified_user_is_silent(client, publisher):
    ac, db, _ = client
    await make_user(db, email="v@example.com", email_verified=True)
    resp = await ac.post("/resend-verification", json={"email": "v@example.com"})
    assert resp.status_code == 202
    assert publisher.calls == []


async def test_resend_for_unknown_email_is_silent(client, publisher):
    ac, _, _ = client
    resp = await ac.post("/resend-verification", json={"email": "ghost@example.com"})
    assert resp.status_code == 202
    assert publisher.calls == []


async def test_resend_response_is_identical_regardless_of_account_state(
    client, publisher
):
    ac, db, _ = client
    await make_user(db, email="known@example.com", email_verified=False)
    existing = await ac.post(
        "/resend-verification", json={"email": "known@example.com"}
    )
    unknown = await ac.post("/resend-verification", json={"email": "ghost@example.com"})
    assert existing.status_code == unknown.status_code == 202
    assert existing.content == unknown.content == b""


async def test_resend_is_throttled_per_address(client, publisher):
    ac, db, _ = client
    await make_user(db, email="spam@example.com", email_verified=False)
    for _ in range(6):
        await ac.post("/resend-verification", json={"email": "spam@example.com"})
    # capped at the default MAX_RESEND_ATTEMPTS
    from app.core.auth.service import MAX_RESEND_ATTEMPTS

    assert len(publisher.calls) == MAX_RESEND_ATTEMPTS


async def test_resend_email_is_case_insensitive(client, publisher):
    ac, db, _ = client
    await make_user(db, email="mix@example.com", email_verified=False)
    resp = await ac.post("/resend-verification", json={"email": "MiX@Example.COM"})
    assert resp.status_code == 202
    assert len(publisher.calls) == 1


async def test_resend_invalid_email_rejected(client):
    ac, _, _ = client
    resp = await ac.post("/resend-verification", json={"email": "not-an-email"})
    assert resp.status_code == 422
