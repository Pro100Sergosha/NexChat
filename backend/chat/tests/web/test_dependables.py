"""FastAPI dependencies — the auth gate for every protected route.

Spec: dependencies raise DOMAIN exceptions (NotAuthenticated, TokenInvalid,
TokenExpired) instead of bare HTTPException, so the shared exception handler
renders the {code, message} contract everywhere. Chat has no user table and
does not check auth's Redis blacklist (see tests/unit/test_token_validation.py)
— get_current_user_id only decodes+validates the token and returns `sub`
as-is, it never looks anything up.
"""

from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt

from app.core.chat.exceptions import TokenExpired, TokenInvalid
from app.core.chat.security import TokenVerifier
from app.core.config import settings
from app.infra.web.dependables import get_access_token, get_current_user_id
from tests.conftest import make_token


def _not_authenticated() -> type:
    # Lazy import: the class is part of the spec and may not exist yet (TDD red).
    from app.core.chat.exceptions import NotAuthenticated

    return NotAuthenticated


# ---------------------------------------------------------------------------
# get_access_token — extracting the bearer token from the header
# ---------------------------------------------------------------------------


class TestGetAccessToken:
    def test_returns_token_from_bearer_header(self):
        assert get_access_token("Bearer abc.def.ghi") == "abc.def.ghi"

    def test_scheme_is_case_insensitive(self):
        assert get_access_token("bearer t1") == "t1"
        assert get_access_token("BEARER t2") == "t2"

    def test_missing_header_raises_not_authenticated(self):
        with pytest.raises(_not_authenticated()):
            get_access_token(None)

    def test_non_bearer_scheme_raises_not_authenticated(self):
        with pytest.raises(_not_authenticated()):
            get_access_token("Basic dXNlcjpwYXNz")

    def test_bare_token_without_scheme_raises_not_authenticated(self):
        with pytest.raises(_not_authenticated()):
            get_access_token("abc.def.ghi")


# ---------------------------------------------------------------------------
# get_current_user_id — full token → user id resolution
# ---------------------------------------------------------------------------


class TestGetCurrentUserId:
    def setup_method(self):
        self.verifier = TokenVerifier(settings)

    async def _call(self, token: str) -> str:
        return await get_current_user_id(token, self.verifier)

    async def test_valid_access_token_returns_sub(self):
        token = make_token(sub="user-42")
        assert await self._call(token) == "user-42"

    async def test_garbage_token_raises_invalid(self):
        with pytest.raises(TokenInvalid):
            await self._call("not-a-jwt")

    async def test_wrong_signature_raises_invalid(self):
        forged = make_token(sub="user-1", secret="attacker-secret")
        with pytest.raises(TokenInvalid):
            await self._call(forged)

    async def test_expired_token_raises_expired(self):
        expired = make_token(sub="user-1", expires_in=-60)
        with pytest.raises(TokenExpired):
            await self._call(expired)

    async def test_refresh_token_raises_invalid(self):
        refresh = make_token(sub="user-1", token_type="refresh")
        with pytest.raises(TokenInvalid):
            await self._call(refresh)

    async def test_missing_sub_raises_invalid(self):
        now = datetime.now(UTC)
        token = jwt.encode(
            {"type": "access", "iat": now, "exp": now + timedelta(minutes=5)},
            settings.JWT_SECRET_KEY,
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(TokenInvalid):
            await self._call(token)
