from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from jose import jwt

from app.core.auth.exceptions import (
    InvalidCredentials,
    TokenExpired,
    TokenInvalid,
    TokenRevoked,
    TooManyAttempts,
    UserAlreadyExists,
)
from app.core.auth.model import User
from app.core.auth.security import (
    REFRESH_TOKEN_TYPE,
    PasswordHasher,
    TokenService,
)
from app.core.auth.service import AuthService
from app.core.config import settings
from tests.conftest import FakeBlacklist, FakeLoginRateLimiter


def _user(email: str = "user@example.com", password: str = "password123") -> User:
    return User(
        id=uuid4(),
        email=email,
        hashed_password=PasswordHasher().hash(password),
        created_at=datetime.now(UTC),
    )


def _service(
    user_repo: AsyncMock,
    blacklist=None,
    rate_limiter=None,
    max_login_attempts: int = 5,
) -> AuthService:
    return AuthService(
        user_repo=user_repo,
        blacklist=blacklist or FakeBlacklist(),
        tokens=TokenService(settings),
        hasher=PasswordHasher(),
        rate_limiter=rate_limiter or FakeLoginRateLimiter(),
        max_login_attempts=max_login_attempts,
    )


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------


class TestRegister:
    async def test_creates_user_when_email_free(self):
        repo = AsyncMock()
        repo.get_by_email.return_value = None
        created = _user()
        repo.create.return_value = created

        service = _service(repo)
        result = await service.register("user@example.com", "password123")

        assert result is created
        repo.create.assert_awaited_once()

    async def test_password_is_bcrypt_hashed_before_persisting(self):
        repo = AsyncMock()
        repo.get_by_email.return_value = None
        repo.create.return_value = _user()

        service = _service(repo)
        await service.register("user@example.com", "password123")

        _email, hashed = repo.create.await_args.args
        assert hashed != "password123"
        # a real bcrypt hash of the original password, not just any string
        assert PasswordHasher().verify("password123", hashed) is True

    async def test_email_is_normalized_to_lowercase(self):
        repo = AsyncMock()
        repo.get_by_email.return_value = None
        repo.create.return_value = _user()

        service = _service(repo)
        await service.register("MiXeD@Example.COM", "password123")

        repo.get_by_email.assert_awaited_once_with("mixed@example.com")
        email, _hashed = repo.create.await_args.args
        assert email == "mixed@example.com"

    async def test_duplicate_email_raises(self):
        repo = AsyncMock()
        repo.get_by_email.return_value = _user()

        service = _service(repo)
        with pytest.raises(UserAlreadyExists):
            await service.register("user@example.com", "password123")
        repo.create.assert_not_called()


# ---------------------------------------------------------------------------
# login
# ---------------------------------------------------------------------------


class TestLogin:
    async def test_valid_credentials_returns_pair(self):
        repo = AsyncMock()
        repo.get_by_email.return_value = _user(password="password123")

        service = _service(repo)
        pair = await service.login("user@example.com", "password123")

        assert pair.access_token
        assert pair.refresh_token
        assert pair.token_type == "bearer"

    async def test_tokens_are_bound_to_the_user(self):
        repo = AsyncMock()
        user = _user(password="password123")
        repo.get_by_email.return_value = user

        service = _service(repo)
        pair = await service.login("user@example.com", "password123")

        tokens = TokenService(settings)
        assert tokens.decode(pair.access_token)["sub"] == str(user.id)
        assert tokens.decode(pair.refresh_token)["sub"] == str(user.id)

    async def test_email_lookup_is_lowercased(self):
        repo = AsyncMock()
        repo.get_by_email.return_value = _user(password="password123")

        service = _service(repo)
        await service.login("USER@Example.COM", "password123")

        repo.get_by_email.assert_awaited_once_with("user@example.com")

    async def test_unknown_email_raises(self):
        repo = AsyncMock()
        repo.get_by_email.return_value = None

        service = _service(repo)
        with pytest.raises(InvalidCredentials):
            await service.login("nobody@example.com", "password123")

    async def test_wrong_password_raises(self):
        repo = AsyncMock()
        repo.get_by_email.return_value = _user(password="password123")

        service = _service(repo)
        with pytest.raises(InvalidCredentials):
            await service.login("user@example.com", "wrong-password")

    async def test_corrupt_stored_hash_raises_invalid_credentials(self):
        """A corrupt hash in the DB reads as a failed login, not a 500."""
        repo = AsyncMock()
        broken = User(
            id=uuid4(),
            email="user@example.com",
            hashed_password="not-a-bcrypt-hash",
            created_at=datetime.now(UTC),
        )
        repo.get_by_email.return_value = broken

        service = _service(repo)
        with pytest.raises(InvalidCredentials):
            await service.login("user@example.com", "password123")


# ---------------------------------------------------------------------------
# login rate limiting — lockout after repeated failures per identity
# ---------------------------------------------------------------------------


class TestLoginRateLimit:
    async def test_lockout_after_max_failed_attempts(self):
        repo = AsyncMock()
        repo.get_by_email.return_value = _user(password="password123")
        service = _service(repo, max_login_attempts=3)

        for _ in range(3):
            with pytest.raises(InvalidCredentials):
                await service.login("user@example.com", "wrong")
        # the 4th attempt is blocked before credentials are even checked
        with pytest.raises(TooManyAttempts):
            await service.login("user@example.com", "wrong")

    async def test_lockout_blocks_even_a_correct_password(self):
        repo = AsyncMock()
        repo.get_by_email.return_value = _user(password="password123")
        service = _service(repo, max_login_attempts=3)

        for _ in range(3):
            with pytest.raises(InvalidCredentials):
                await service.login("user@example.com", "wrong")
        with pytest.raises(TooManyAttempts):
            await service.login("user@example.com", "password123")

    async def test_lockout_short_circuits_before_the_repository(self):
        """A locked identity must not reach the DB — save the round trip."""
        repo = AsyncMock()
        repo.get_by_email.return_value = _user(password="password123")
        service = _service(repo, max_login_attempts=2)

        for _ in range(2):
            with pytest.raises(InvalidCredentials):
                await service.login("user@example.com", "wrong")
        repo.get_by_email.reset_mock()
        with pytest.raises(TooManyAttempts):
            await service.login("user@example.com", "wrong")
        repo.get_by_email.assert_not_called()

    async def test_successful_login_resets_the_counter(self):
        repo = AsyncMock()
        repo.get_by_email.return_value = _user(password="password123")
        limiter = FakeLoginRateLimiter()
        service = _service(repo, rate_limiter=limiter, max_login_attempts=3)

        for _ in range(2):
            with pytest.raises(InvalidCredentials):
                await service.login("user@example.com", "wrong")
        await service.login("user@example.com", "password123")
        assert await limiter.count("user@example.com") == 0

    async def test_failures_are_tracked_per_identity(self):
        repo = AsyncMock()
        repo.get_by_email.return_value = None
        service = _service(repo, max_login_attempts=2)

        for _ in range(2):
            with pytest.raises(InvalidCredentials):
                await service.login("a@example.com", "wrong")
        # a different identity is unaffected by a@example.com's failures
        with pytest.raises(InvalidCredentials):
            await service.login("b@example.com", "wrong")

    async def test_counter_keys_on_normalized_email(self):
        repo = AsyncMock()
        repo.get_by_email.return_value = None
        limiter = FakeLoginRateLimiter()
        service = _service(repo, rate_limiter=limiter, max_login_attempts=5)

        with pytest.raises(InvalidCredentials):
            await service.login("  MiXeD@Example.COM ", "wrong")
        assert await limiter.count("mixed@example.com") == 1


# ---------------------------------------------------------------------------
# refresh
# ---------------------------------------------------------------------------


class TestRefresh:
    async def test_valid_refresh_rotates_pair(self):
        repo = AsyncMock()
        blacklist = FakeBlacklist()
        service = _service(repo, blacklist)
        tokens = TokenService(settings)
        refresh_token = tokens.create_refresh("user-1")

        pair = await service.refresh(refresh_token)

        assert pair.access_token
        assert pair.refresh_token
        # rotation: old refresh jti is now revoked
        old_jti = tokens.decode(refresh_token)["jti"]
        assert await blacklist.is_revoked(old_jti) is True

    async def test_new_pair_has_fresh_jti(self):
        repo = AsyncMock()
        service = _service(repo)
        tokens = TokenService(settings)
        refresh_token = tokens.create_refresh("user-1")

        pair = await service.refresh(refresh_token)

        old_jti = tokens.decode(refresh_token)["jti"]
        assert tokens.decode(pair.refresh_token)["jti"] != old_jti
        assert tokens.decode(pair.access_token)["jti"] != old_jti

    async def test_access_token_rejected_as_refresh(self):
        repo = AsyncMock()
        service = _service(repo)
        access_token = TokenService(settings).create_access("user-1")

        with pytest.raises(TokenInvalid):
            await service.refresh(access_token)

    async def test_expired_refresh_raises_expired(self):
        repo = AsyncMock()
        service = _service(repo)
        now = datetime.now(UTC)
        expired = jwt.encode(
            {
                "sub": "user-1",
                "jti": uuid4().hex,
                "type": REFRESH_TOKEN_TYPE,
                "iat": now - timedelta(days=8),
                "exp": now - timedelta(days=1),
            },
            settings.JWT_SECRET_KEY,
            algorithm=settings.jwt_algorithm,
        )

        with pytest.raises(TokenExpired):
            await service.refresh(expired)

    async def test_revoked_refresh_raises(self):
        repo = AsyncMock()
        blacklist = FakeBlacklist()
        service = _service(repo, blacklist)
        tokens = TokenService(settings)
        refresh_token = tokens.create_refresh("user-1")
        await blacklist.revoke(tokens.decode(refresh_token)["jti"], 3600)

        with pytest.raises(TokenRevoked):
            await service.refresh(refresh_token)

    async def test_reusing_rotated_refresh_raises(self):
        repo = AsyncMock()
        blacklist = FakeBlacklist()
        service = _service(repo, blacklist)
        refresh_token = TokenService(settings).create_refresh("user-1")

        await service.refresh(refresh_token)  # first use — rotates + revokes
        with pytest.raises(TokenRevoked):
            await service.refresh(refresh_token)  # replay must fail


# ---------------------------------------------------------------------------
# logout
# ---------------------------------------------------------------------------


class TestLogout:
    async def test_revokes_both_tokens(self):
        repo = AsyncMock()
        blacklist = FakeBlacklist()
        service = _service(repo, blacklist)
        tokens = TokenService(settings)
        access = tokens.create_access("user-1")
        refresh = tokens.create_refresh("user-1")

        await service.logout(refresh, access)

        assert await blacklist.is_revoked(tokens.decode(access)["jti"]) is True
        assert await blacklist.is_revoked(tokens.decode(refresh)["jti"]) is True

    async def test_refresh_after_logout_raises_revoked(self):
        repo = AsyncMock()
        blacklist = FakeBlacklist()
        service = _service(repo, blacklist)
        tokens = TokenService(settings)
        access = tokens.create_access("user-1")
        refresh = tokens.create_refresh("user-1")

        await service.logout(refresh, access)
        with pytest.raises(TokenRevoked):
            await service.refresh(refresh)

    async def test_swapped_token_types_raise(self):
        repo = AsyncMock()
        service = _service(repo)
        tokens = TokenService(settings)
        access = tokens.create_access("user-1")
        refresh = tokens.create_refresh("user-1")

        # refresh_token arg gets an access token → type mismatch
        with pytest.raises(TokenInvalid):
            await service.logout(access, refresh)


# ---------------------------------------------------------------------------
# _revoke edge cases — blacklist hygiene
# ---------------------------------------------------------------------------


class TestRevoke:
    """Private helper, but its edge cases guard Redis from useless entries."""

    def setup_method(self):
        self.blacklist = FakeBlacklist()
        self.service = _service(AsyncMock(), self.blacklist)

    async def test_already_expired_claims_are_not_blacklisted(self):
        """ttl <= 0 → the token is dead anyway; storing it would be waste."""
        past = datetime.now(UTC) - timedelta(hours=1)
        await self.service._revoke({"jti": "dead-jti", "exp": past.timestamp()})
        assert await self.blacklist.is_revoked("dead-jti") is False

    async def test_missing_jti_is_skipped_quietly(self):
        future = datetime.now(UTC) + timedelta(hours=1)
        await self.service._revoke({"exp": future.timestamp()})  # no crash

    async def test_missing_exp_is_skipped_quietly(self):
        await self.service._revoke({"jti": "some-jti"})  # no crash
        assert await self.blacklist.is_revoked("some-jti") is False
