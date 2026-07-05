"""Token extraction + access-token verification dependables in isolation."""

import pytest

from app.core.config import settings
from app.core.notifications.exceptions import (
    NotAuthenticated,
    TokenExpired,
    TokenInvalid,
)
from app.core.notifications.security import TokenVerifier
from app.infra.web.dependables import get_access_token, get_current_user_id
from tests.conftest import make_token

verifier = TokenVerifier(settings)


def test_get_access_token_missing_header():
    with pytest.raises(NotAuthenticated):
        get_access_token(None)


def test_get_access_token_wrong_scheme():
    with pytest.raises(NotAuthenticated):
        get_access_token("Basic abc")


def test_get_access_token_bearer():
    assert get_access_token("Bearer xyz") == "xyz"


def test_current_user_id_from_valid_token():
    token = make_token(sub="user-42")
    assert get_current_user_id(token, verifier) == "user-42"


def test_current_user_id_expired():
    token = make_token(expires_in=-10)
    with pytest.raises(TokenExpired):
        get_current_user_id(token, verifier)


def test_current_user_id_wrong_type():
    token = make_token(token_type="refresh")
    with pytest.raises(TokenInvalid):
        get_current_user_id(token, verifier)


def test_current_user_id_forged_signature():
    token = make_token(secret="not-the-real-secret")
    with pytest.raises(TokenInvalid):
        get_current_user_id(token, verifier)
