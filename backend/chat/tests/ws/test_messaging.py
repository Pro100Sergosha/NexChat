"""WS message frames.

Client sends either `{"recipient_id": ..., "content": ...}` (resolves or
creates the 1:1 conversation implicitly) or `{"conversation_id": ...,
"content": ...}` (continuing a known conversation — server still checks
the sender is actually a participant). The server acks the sender with the
persisted message frame and broadcasts the same frame to the recipient's
connections if they're online.

Bad payloads close the socket (4422) rather than sending an error frame —
same close-code convention as the handshake (see test_handshake.py).
"""

import pytest
from starlette.websockets import WebSocketDisconnect

from tests.conftest import make_token


def _expect_close(ws_client, url, send, *, code, raw=False):
    with ws_client.websocket_connect(url) as ws:
        ws.send_text(send) if raw else ws.send_json(send)
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_json()
    assert exc_info.value.code == code


def test_new_recipient_creates_conversation(ws_client, db_session):
    token = make_token(sub="user-a")
    with ws_client.websocket_connect(f"/ws?token={token}") as ws:
        ws.send_json({"recipient_id": "user-b", "content": "hi"})
        ack = ws.receive_json()

    assert ack["sender_id"] == "user-a"
    assert ack["content"] == "hi"
    assert ack["id"] is not None
    assert ack["conversation_id"] is not None


def test_second_message_reuses_same_conversation(ws_client, db_session):
    token = make_token(sub="user-a")
    with ws_client.websocket_connect(f"/ws?token={token}") as ws:
        ws.send_json({"recipient_id": "user-b", "content": "hi"})
        first_ack = ws.receive_json()
        ws.send_json({"recipient_id": "user-b", "content": "again"})
        second_ack = ws.receive_json()

    assert first_ack["conversation_id"] == second_ack["conversation_id"]


def test_existing_conversation_id_accepted(ws_client):
    token = make_token(sub="user-a")
    with ws_client.websocket_connect(f"/ws?token={token}") as ws:
        ws.send_json({"recipient_id": "user-b", "content": "hi"})
        first_ack = ws.receive_json()
        assert "conversation_id" in first_ack, f"unexpected response: {first_ack}"
        conversation_id = first_ack["conversation_id"]

        ws.send_json({"conversation_id": conversation_id, "content": "again"})
        ack = ws.receive_json()

    assert ack["conversation_id"] == conversation_id


def test_recipient_online_receives_broadcast(ws_client, db_session):
    sender_token = make_token(sub="user-a")
    recipient_token = make_token(sub="user-b")
    with ws_client.websocket_connect(f"/ws?token={recipient_token}") as recipient_ws:
        with ws_client.websocket_connect(f"/ws?token={sender_token}") as sender_ws:
            sender_ws.send_json({"recipient_id": "user-b", "content": "hi"})
            sender_ws.receive_json()  # ack to sender
            # Read the broadcast while sender_ws is still open — closing it
            # first cancels the server-side task via the portal, which can
            # race ahead of (and abort) the broadcast send that follows the
            # ack in the same handler iteration.
            broadcast = recipient_ws.receive_json()

    assert broadcast["content"] == "hi"
    assert broadcast["sender_id"] == "user-a"


def test_recipient_offline_message_still_persisted_no_error(ws_client, db_session):
    token = make_token(sub="user-a")
    with ws_client.websocket_connect(f"/ws?token={token}") as ws:
        ws.send_json({"recipient_id": "user-b", "content": "hi"})
        ack = ws.receive_json()  # no crash even though user-b has no connection

    assert ack["content"] == "hi"


def test_sender_not_participant_of_conversation_id_rejected(ws_client):
    owner_token = make_token(sub="user-a")
    with ws_client.websocket_connect(f"/ws?token={owner_token}") as owner_ws:
        owner_ws.send_json({"recipient_id": "user-b", "content": "hi"})
        owner_ack = owner_ws.receive_json()
        assert "conversation_id" in owner_ack, f"unexpected response: {owner_ack}"
        conversation_id = owner_ack["conversation_id"]

    outsider_token = make_token(sub="user-c")
    _expect_close(
        ws_client,
        f"/ws?token={outsider_token}",
        {"conversation_id": conversation_id, "content": "hi"},
        code=4403,
    )


def test_empty_content_rejected(ws_client, db_session):
    token = make_token(sub="user-a")
    _expect_close(
        ws_client,
        f"/ws?token={token}",
        {"recipient_id": "user-b", "content": ""},
        code=4422,
    )


def test_whitespace_only_content_rejected(ws_client, db_session):
    token = make_token(sub="user-a")
    _expect_close(
        ws_client,
        f"/ws?token={token}",
        {"recipient_id": "user-b", "content": "   "},
        code=4422,
    )


def test_content_over_max_length_rejected(ws_client, db_session):
    from app.core.config import settings

    token = make_token(sub="user-a")
    _expect_close(
        ws_client,
        f"/ws?token={token}",
        {"recipient_id": "user-b", "content": "x" * (settings.MESSAGE_MAX_LENGTH + 1)},
        code=4422,
    )


def test_malformed_json_payload_rejected(ws_client, db_session):
    token = make_token(sub="user-a")
    _expect_close(ws_client, f"/ws?token={token}", "not json", code=4422, raw=True)


def test_missing_recipient_and_conversation_id_rejected(ws_client, db_session):
    token = make_token(sub="user-a")
    _expect_close(ws_client, f"/ws?token={token}", {"content": "hi"}, code=4422)


def test_self_message_rejected(ws_client, db_session):
    token = make_token(sub="user-a")
    _expect_close(
        ws_client,
        f"/ws?token={token}",
        {"recipient_id": "user-a", "content": "hi"},
        code=4422,
    )


def test_nonexistent_conversation_id_rejected(ws_client, db_session):
    token = make_token(sub="user-a")
    _expect_close(
        ws_client,
        f"/ws?token={token}",
        {"conversation_id": 999999, "content": "hi"},
        code=4403,
    )
