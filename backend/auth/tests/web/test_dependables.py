"""FastAPI dependencies — the auth gate for every protected route.

Spec: the dependencies raise DOMAIN exceptions (NotAuthenticated, TokenInvalid,
TokenExpired, TokenRevoked) instead of bare HTTPException, so the shared
exception handler renders the {code, message} contract everywhere.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.auth.exceptions import TokenExpired, TokenInvalid, TokenRevoked
from app.core.auth.model import User
from app.core.auth.security import PasswordHasher, TokenService
from app.core.config import settings
from app.infra.web.dependables import get_access_token, get_current_user
from tests.conftest import FakeBlacklist, InMemoryUserRepository, make_token


def _not_authenticated() -> type:
    # Lazy import: the class is part of the spec and may not exist yet (TDD red).
    from app.core.auth.exceptions import NotAuthenticated

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
# get_current_user — full token → user resolution
# ---------------------------------------------------------------------------


def _seeded_repo() -> tuple[InMemoryUserRepository, User]:
    repo = InMemoryUserRepository()
    user = repo.seed(
        User(
            id=uuid4(),
            email="dep@example.com",
            username="depuser",
            hashed_password=PasswordHasher().hash("password123"),
            created_at=datetime.now(UTC),
            email_verified=True,
            token_version=0,
        )
    )
    return repo, user


class TestGetCurrentUser:
    def setup_method(self):
        self.tokens = TokenService(settings)
        self.blacklist = FakeBlacklist()
        self.repo, self.user = _seeded_repo()

    async def _call(self, token: str) -> User:
        return await get_current_user(token, self.tokens, self.blacklist, self.repo)

    async def test_valid_access_token_returns_user(self):
        token = self.tokens.create_access(str(self.user.id))
        assert await self._call(token) == self.user

    async def test_garbage_token_raises_invalid(self):
        with pytest.raises(TokenInvalid):
            await self._call("not-a-jwt")

    async def test_wrong_signature_raises_invalid(self):
        forged = make_token(sub=str(self.user.id), secret="attacker-secret")
        with pytest.raises(TokenInvalid):
            await self._call(forged)

    async def test_expired_token_raises_expired(self):
        expired = make_token(sub=str(self.user.id), expires_in=-60)
        with pytest.raises(TokenExpired):
            await self._call(expired)

    async def test_refresh_token_raises_invalid(self):
        refresh = self.tokens.create_refresh(str(self.user.id))
        with pytest.raises(TokenInvalid):
            await self._call(refresh)

    async def test_revoked_token_raises_revoked(self):
        token = self.tokens.create_access(str(self.user.id))
        jti = self.tokens.decode(token)["jti"]
        await self.blacklist.revoke(jti, 3600)
        with pytest.raises(TokenRevoked):
            await self._call(token)

    async def test_unknown_subject_raises_invalid(self):
        """Valid signature but the user was deleted — token no longer works."""
        ghost = self.tokens.create_access(str(uuid4()))
        with pytest.raises(TokenInvalid):
            await self._call(ghost)
