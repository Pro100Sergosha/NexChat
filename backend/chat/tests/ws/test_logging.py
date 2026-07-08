"""WS logging — connection lifecycle and message events are logged, never content.

* A valid handshake logs ``ws connected`` and, on teardown, ``ws disconnected``
  (both with the user id) on ``app.infra.web.ws``.
* A rejected handshake logs a ``handshake rejected`` warning.
* A sent message logs ``message sent`` (ids only) on ``app.core.chat.service`` —
  the message body is never written to the log.
"""

import logging

from tests.conftest import make_token

_WS_LOGGER = "app.infra.web.ws"
_SERVICE_LOGGER = "app.core.chat.service"


def test_connect_and_disconnect_are_logged(ws_client, caplog):
    token = make_token(sub="user-a")
    with (
        caplog.at_level(logging.INFO, logger=_WS_LOGGER),
        ws_client.websocket_connect(f"/ws?token={token}"),
    ):
        pass
    msgs = [r.getMessage() for r in caplog.records if r.name == _WS_LOGGER]
    assert any("ws connected" in m and "user-a" in m for m in msgs)
    assert any("ws disconnected" in m and "user-a" in m for m in msgs)


def test_rejected_handshake_is_logged(ws_client, caplog):
    with caplog.at_level(logging.WARNING):
        try:
            with ws_client.websocket_connect("/ws?token=garbage"):
                pass
        except Exception:
            pass
    msgs = [r.getMessage() for r in caplog.records]
    assert any("handshake rejected" in m for m in msgs)


def test_message_send_is_logged_without_content(ws_client, db_session, caplog):
    token = make_token(sub="user-a")
    secret = "top-secret-body-xyz"
    with (
        caplog.at_level(logging.INFO),
        ws_client.websocket_connect(f"/ws?token={token}") as ws,
    ):
        ws.send_json({"recipient_id": "user-b", "content": secret})
        ws.receive_json()
    service_msgs = [r.getMessage() for r in caplog.records if r.name == _SERVICE_LOGGER]
    assert any("message sent" in m for m in service_msgs)
    all_msgs = " ".join(r.getMessage() for r in caplog.records)
    assert secret not in all_msgs
