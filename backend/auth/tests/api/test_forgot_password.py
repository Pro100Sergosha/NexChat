"""POST /forgot-password — contract:

* Body ``{email}``; always 202 with an empty body (anti-enumeration).
* Only a real account triggers an actual reset email; unknown / throttled
  addresses are silently ignored — the response never differs.
"""

from tests.conftest import make_user


async def test_forgot_for_existing_user_publishes_reset(client, publisher):
    ac, db, _ = client
    user, _ = await make_user(db, email="u@example.com")
    resp = await ac.post("/forgot-password", json={"email": "u@example.com"})
    assert resp.status_code == 202
    assert len(publisher.reset_calls) == 1
    assert publisher.reset_calls[0]["user_id"] == str(user.id)
    assert "token=" in publisher.reset_calls[0]["reset_url"]


async def test_forgot_for_unknown_email_is_silent(client, publisher):
    ac, _, _ = client
    resp = await ac.post("/forgot-password", json={"email": "ghost@example.com"})
    assert resp.status_code == 202
    assert publisher.reset_calls == []


async def test_forgot_response_identical_regardless_of_account(client, publisher):
    ac, db, _ = client
    await make_user(db, email="known@example.com")
    existing = await ac.post("/forgot-password", json={"email": "known@example.com"})
    unknown = await ac.post("/forgot-password", json={"email": "ghost@example.com"})
    assert existing.status_code == unknown.status_code == 202
    assert existing.content == unknown.content == b""


async def test_forgot_is_throttled_per_address(client, publisher):
    ac, db, _ = client
    await make_user(db, email="spam@example.com")
    for _ in range(6):
        await ac.post("/forgot-password", json={"email": "spam@example.com"})
    from app.core.auth.service import MAX_RESET_ATTEMPTS

    assert len(publisher.reset_calls) == MAX_RESET_ATTEMPTS


async def test_forgot_email_is_case_insensitive(client, publisher):
    ac, db, _ = client
    await make_user(db, email="mix@example.com")
    resp = await ac.post("/forgot-password", json={"email": "MiX@Example.COM"})
    assert resp.status_code == 202
    assert len(publisher.reset_calls) == 1


async def test_forgot_invalid_email_rejected(client):
    ac, _, _ = client
    resp = await ac.post("/forgot-password", json={"email": "not-an-email"})
    assert resp.status_code == 422
