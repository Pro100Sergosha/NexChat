"""Disconnect cleanup — the `ConnectionManager` entry must go away whether
the client closes cleanly or the server closes the socket on error
(see test_messaging.py's 4422 cases)."""

import pytest
from starlette.websockets import WebSocketDisconnect

from tests.conftest import make_token


def test_disconnect_removes_connection(ws_client, connection_manager):
    token = make_token(sub="user-a")
    with ws_client.websocket_connect(f"/ws?token={token}"):
        pass  # graceful close on context exit

    assert connection_manager._connections.get("user-a", set()) == set()


def test_multi_device_disconnect_of_one_keeps_others_online(
    ws_client, connection_manager
):
    token = make_token(sub="user-a")
    with ws_client.websocket_connect(f"/ws?token={token}") as outer:
        with ws_client.websocket_connect(f"/ws?token={token}"):
            pass  # inner connection closes first

        assert connection_manager._connections.get("user-a", set()) != set()
        assert outer is not None

    assert connection_manager._connections.get("user-a", set()) == set()


def test_error_close_still_cleans_up_connection(ws_client, connection_manager):
    token = make_token(sub="user-a")
    with pytest.raises(WebSocketDisconnect):
        with ws_client.websocket_connect(f"/ws?token={token}") as ws:
            ws.send_json(
                {"recipient_id": "user-a", "content": "hi"}
            )  # self-message: 4422
            ws.receive_json()

    assert connection_manager._connections.get("user-a", set()) == set()


def test_two_different_users_disconnect_independently(ws_client, connection_manager):
    token_a = make_token(sub="user-a")
    token_b = make_token(sub="user-b")
    with ws_client.websocket_connect(f"/ws?token={token_a}"):
        with ws_client.websocket_connect(f"/ws?token={token_b}"):
            pass  # user-b disconnects

        assert connection_manager._connections.get("user-b", set()) == set()
        assert connection_manager._connections.get("user-a", set()) != set()

    assert connection_manager._connections.get("user-a", set()) == set()
