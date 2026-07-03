"""ws://.../ws?token=<jwt> — WebSocket handshake.

WS has no HTTP status/JSON body, so auth failures use custom close codes
(see tests/conftest.py `assert_ws_close`):
  * 4401 — missing/invalid/expired/wrong-signature/wrong-type token
  * 4403 — sender not a participant of a referenced conversation (test_messaging.py)
  * 4422 — malformed/oversized payload (test_messaging.py)

A rejection during the handshake closes before `.accept()`, so entering
the `websocket_connect` context itself raises `WebSocketDisconnect`.
"""

from tests.conftest import assert_ws_close, make_token


def test_valid_token_accepted(ws_client):
    token = make_token(sub="user-a")
    with ws_client.websocket_connect(f"/ws?token={token}") as ws:
        assert ws is not None


def test_missing_token_rejected(ws_client):
    assert_ws_close(ws_client, "/ws", 4401)


def test_garbage_token_rejected(ws_client):
    assert_ws_close(ws_client, "/ws?token=not-a-real-jwt", 4401)


def test_expired_token_rejected(ws_client):
    token = make_token(sub="user-a", expires_in=-60)
    assert_ws_close(ws_client, f"/ws?token={token}", 4401)


def test_wrong_signature_token_rejected(ws_client):
    token = make_token(sub="user-a", secret="wrong-secret")
    assert_ws_close(ws_client, f"/ws?token={token}", 4401)


def test_refresh_token_used_as_access_rejected(ws_client):
    token = make_token(sub="user-a", token_type="refresh")
    assert_ws_close(ws_client, f"/ws?token={token}", 4401)


def test_multi_device_connections_both_accepted(ws_client):
    token = make_token(sub="user-a")
    with (
        ws_client.websocket_connect(f"/ws?token={token}") as ws1,
        ws_client.websocket_connect(f"/ws?token={token}") as ws2,
    ):
        assert ws1 is not None
        assert ws2 is not None
