"""GET /health — liveness probe used by the compose healthcheck."""


async def test_health_ok(client):
    ac, _db, _fakes = client
    resp = await ac.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
