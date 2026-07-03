"""GET /health — liveness probe, no auth."""


async def test_health_ok(client):
    ac, _, _ = client
    resp = await ac.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
