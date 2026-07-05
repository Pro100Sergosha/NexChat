"""GET /events handshake — the token is validated (via ?token=) before any
stream starts, so a bad token is a plain 401 the EventSource surfaces as
onerror. Close-code catalog note: SSE has no WS close codes; auth failure is a
normal HTTP 401 with the {code, message} body."""

from tests.conftest import make_token


async def test_missing_token_is_401(client):
    ac, _db, _fakes = client
    resp = await ac.get("/events")
    assert resp.status_code == 401
    assert resp.json()["code"] == "token_invalid"


async def test_garbage_token_is_401(client):
    ac, _db, _fakes = client
    resp = await ac.get("/events?token=not-a-jwt")
    assert resp.status_code == 401
    assert resp.json()["code"] == "token_invalid"


async def test_expired_token_is_401(client):
    ac, _db, _fakes = client
    resp = await ac.get(f"/events?token={make_token(expires_in=-10)}")
    assert resp.status_code == 401
    assert resp.json()["code"] == "token_expired"


async def test_wrong_token_type_is_401(client):
    ac, _db, _fakes = client
    resp = await ac.get(f"/events?token={make_token(token_type='refresh')}")
    assert resp.status_code == 401
    assert resp.json()["code"] == "token_invalid"
