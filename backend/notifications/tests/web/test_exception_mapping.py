"""The pinned error catalog: every domain exception → its HTTP status, stable
code, and human-readable message. One table, checked exhaustively."""

import json

import pytest

from app.core.notifications.exceptions import (
    DeviceTokenNotFound,
    NotAuthenticated,
    NotAuthorized,
    NotificationNotFound,
    TokenExpired,
    TokenInvalid,
)
from app.infra.web.responses import app_exception_handler

CATALOG = [
    (NotificationNotFound, 404, "notification_not_found"),
    (DeviceTokenNotFound, 404, "device_token_not_found"),
    (NotAuthorized, 403, "not_authorized"),
    (TokenExpired, 401, "token_expired"),
    (TokenInvalid, 401, "token_invalid"),
    (NotAuthenticated, 401, "not_authenticated"),
]


@pytest.mark.parametrize(("exc_class", "status", "code"), CATALOG)
def test_exception_maps_to_contract(exc_class, status, code):
    response = app_exception_handler(None, exc_class())

    assert response.status_code == status
    body = json.loads(response.body)
    assert body["code"] == code
    message = body["message"]
    assert isinstance(message, str) and " " in message
    assert message != code
