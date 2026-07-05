from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from jose import jwt

from app.core.auth.exceptions import (
    EmailAlreadyVerified,
    EmailNotVerified,
    InvalidCredentials,
    TokenExpired,
    TokenInvalid,
    TokenRevoked,
    TooManyAttempts,
    UserAlreadyExists,
    UsernameTaken,
    UserNotFound,
)
from app.core.auth.model import User
from app.core.auth.security import (
    REFRESH_TOKEN_TYPE,
    RESET_TOKEN_TYPE,
    VERIFY_TOKEN_TYPE,
    PasswordHasher,
    TokenService,
)
from app.core.auth.service import AuthService
from app.core.config import settings
from tests.conftest import (
    FakeBlacklist,
    FakeLoginRateLimiter,
    FakeNotificationPublisher,
    InMemoryUserRepository,
)


def _user(
    email: str = "user@example.com",
    username: str = "user",
    password: str = "password123",
    email_verified: bool = True,
    token_version: int = 0,
) -> User:
    return User(
        id=uuid4(),
        email=email,
        username=username,
        hashed_password=PasswordHasher().hash(password),
        created_at=datetime.now(UTC),
        email_verified=email_verified,
        token_version=token_version,
    )


def _service(
    user_repo: AsyncMock,
    blacklist=None,
    rate_limiter=None,
    publisher=None,
    max_login_attempts: int = 5,
    max_resend_attempts: int = 3,
    max_reset_attempts: int = 3,
) -> AuthService:
    return AuthService(
        user_repo=user_repo,
        blacklist=blacklist or FakeBlacklist(),
        tokens=TokenService(settings),
        hasher=PasswordHasher(),
        rate_limiter=rate_limiter or FakeLoginRateLimiter(),
        publisher=publisher or FakeNotificationPublisher(),
        verify_url_base="https://app.test/verify-email",
        reset_url_base="https://app.test/reset-password",
        max_login_attempts=max_login_attempts,
        max_resend_attempts=max_resend_attempts,
        max_reset_attempts=max_reset_attempts,
    )


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------


class TestRegister:
    async def test_creates_user_when_email_free(self):
        repo = AsyncMock()
        repo.get_by_email.return_value = None
        repo.get_by_username.return_value = None
        created = _user()
        repo.create.return_value = created

        service = _service(repo)
        result = await service.register("user@example.com", "newuser", "password123")

        assert result is created
        repo.create.assert_awaited_once()

    async def test_password_is_bcrypt_hashed_before_persisting(self):
        repo = AsyncMock()
        repo.get_by_email.return_value = None
        repo.get_by_username.return_value = None
        repo.create.return_value = _user()

        service = _service(repo)
        await service.register("user@example.com", "newuser", "password123")

        _email, _username, hashed = repo.create.await_args.args
        assert hashed != "password123"
        # a real bcrypt hash of the original password, not just any string
        assert PasswordHasher().verify("password123", hashed) is True

    async def test_email_is_normalized_to_lowercase(self):
        repo = AsyncMock()
        repo.get_by_email.return_value = None
        repo.get_by_username.return_value = None
        repo.create.return_value = _user()

        service = _service(repo)
        await service.register("MiXeD@Example.COM", "newuser", "password123")

        repo.get_by_email.assert_awaited_once_with("mixed@example.com")
        email, _username, _hashed = repo.create.await_args.args
        assert email == "mixed@example.com"

    async def test_duplicate_email_raises(self):
        repo = AsyncMock()
        repo.get_by_email.return_value = _user()

        service = _service(repo)
        with pytest.raises(UserAlreadyExists):
            await service.register("user@example.com", "newuser", "password123")
        repo.create.assert_not_called()

    async def test_duplicate_username_raises(self):
        repo = AsyncMock()
        repo.get_by_email.return_value = None
        repo.get_by_username.return_value = _user()

        service = _service(repo)
        with pytest.raises(UsernameTaken):
            await service.register("free@example.com", "taken", "password123")
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
            username="user",
            hashed_password="not-a-bcrypt-hash",
            created_at=datetime.now(UTC),
            email_verified=True,
            token_version=0,
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


# ---------------------------------------------------------------------------
# email verification — register publishes, login gates, verify confirms
# ---------------------------------------------------------------------------


class TestRegisterSendsVerification:
    async def test_publishes_verification_email_with_token_link(self):
        repo = AsyncMock()
        repo.get_by_email.return_value = None
        repo.get_by_username.return_value = None
        created = _user(email_verified=False)
        repo.create.return_value = created
        publisher = FakeNotificationPublisher()

        service = _service(repo, publisher=publisher)
        await service.register("new@example.com", "newuser", "password123")

        assert len(publisher.calls) == 1
        call = publisher.calls[0]
        assert call["email"] == created.email
        assert call["user_id"] == str(created.id)
        # the link carries a real verify JWT the user can redeem
        token = call["verify_url"].split("token=", 1)[1]
        claims = TokenService(settings).decode(token)
        assert claims["type"] == VERIFY_TOKEN_TYPE
        assert claims["sub"] == str(created.id)

    async def test_publish_failure_does_not_fail_registration(self):
        repo = AsyncMock()
        repo.get_by_email.return_value = None
        repo.get_by_username.return_value = None
        created = _user(email_verified=False)
        repo.create.return_value = created
        publisher = AsyncMock()
        publisher.publish_verification.side_effect = RuntimeError("broker down")

        service = _service(repo, publisher=publisher)
        result = await service.register("new@example.com", "newuser", "password123")

        assert result is created  # best-effort: the user is still created


class TestLoginEmailGate:
    async def test_unverified_user_cannot_login(self):
        repo = AsyncMock()
        repo.get_by_email.return_value = _user(
            password="password123", email_verified=False
        )
        service = _service(repo)
        with pytest.raises(EmailNotVerified):
            await service.login("user@example.com", "password123")

    async def test_verified_user_logs_in(self):
        repo = AsyncMock()
        repo.get_by_email.return_value = _user(
            password="password123", email_verified=True
        )
        service = _service(repo)
        pair = await service.login("user@example.com", "password123")
        assert pair.access_token

    async def test_wrong_password_on_unverified_still_invalid_credentials(self):
        """The verified gate must sit behind the password check (no enumeration)."""
        repo = AsyncMock()
        repo.get_by_email.return_value = _user(
            password="password123", email_verified=False
        )
        service = _service(repo)
        with pytest.raises(InvalidCredentials):
            await service.login("user@example.com", "wrong-password")


class TestVerifyEmail:
    def _seed(
        self, *, email_verified: bool = False
    ) -> tuple[InMemoryUserRepository, User]:
        repo = InMemoryUserRepository()
        user = repo.seed(_user(email_verified=email_verified))
        return repo, user

    async def test_valid_token_marks_verified_and_revokes(self):
        repo, user = self._seed()
        blacklist = FakeBlacklist()
        service = _service(AsyncMock(), blacklist)
        service._users = repo  # use the in-memory repo for get_by_id/set
        token = TokenService(settings).create_verify(str(user.id))

        await service.verify_email(token)

        assert (await repo.get_by_id(user.id)).email_verified is True
        jti = TokenService(settings).decode(token)["jti"]
        assert await blacklist.is_revoked(jti) is True

    async def test_reused_token_raises_already_verified(self):
        repo, user = self._seed()
        service = _service(AsyncMock(), FakeBlacklist())
        service._users = repo
        token = TokenService(settings).create_verify(str(user.id))

        await service.verify_email(token)
        with pytest.raises(EmailAlreadyVerified):
            await service.verify_email(token)

    async def test_already_verified_user_raises(self):
        repo, user = self._seed(email_verified=True)
        service = _service(AsyncMock())
        service._users = repo
        token = TokenService(settings).create_verify(str(user.id))
        with pytest.raises(EmailAlreadyVerified):
            await service.verify_email(token)

    async def test_access_token_rejected(self):
        repo, user = self._seed()
        service = _service(AsyncMock())
        service._users = repo
        access = TokenService(settings).create_access(str(user.id))
        with pytest.raises(TokenInvalid):
            await service.verify_email(access)

    async def test_garbage_token_raises_invalid(self):
        service = _service(AsyncMock())
        with pytest.raises(TokenInvalid):
            await service.verify_email("not-a-jwt")

    async def test_expired_token_raises_expired(self):
        repo, user = self._seed()
        service = _service(AsyncMock())
        service._users = repo
        now = datetime.now(UTC)
        expired = jwt.encode(
            {
                "sub": str(user.id),
                "jti": uuid4().hex,
                "type": VERIFY_TOKEN_TYPE,
                "iat": now - timedelta(days=2),
                "exp": now - timedelta(days=1),
            },
            settings.JWT_SECRET_KEY,
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(TokenExpired):
            await service.verify_email(expired)

    async def test_unknown_subject_raises_invalid(self):
        service = _service(AsyncMock())
        service._users = InMemoryUserRepository()  # empty
        ghost = TokenService(settings).create_verify(str(uuid4()))
        with pytest.raises(TokenInvalid):
            await service.verify_email(ghost)


class TestResendVerification:
    async def test_resends_for_unverified_user(self):
        repo = InMemoryUserRepository()
        user = repo.seed(_user(email="r@example.com", email_verified=False))
        publisher = FakeNotificationPublisher()
        service = _service(AsyncMock(), publisher=publisher)
        service._users = repo

        await service.resend_verification("r@example.com")

        assert len(publisher.calls) == 1
        assert publisher.calls[0]["user_id"] == str(user.id)

    async def test_no_send_for_already_verified(self):
        repo = InMemoryUserRepository()
        repo.seed(_user(email="v@example.com", email_verified=True))
        publisher = FakeNotificationPublisher()
        service = _service(AsyncMock(), publisher=publisher)
        service._users = repo

        await service.resend_verification("v@example.com")
        assert publisher.calls == []

    async def test_no_send_for_unknown_email(self):
        publisher = FakeNotificationPublisher()
        service = _service(AsyncMock(), publisher=publisher)
        service._users = InMemoryUserRepository()

        await service.resend_verification("ghost@example.com")
        assert publisher.calls == []

    async def test_throttled_after_max_attempts(self):
        repo = InMemoryUserRepository()
        repo.seed(_user(email="r@example.com", email_verified=False))
        publisher = FakeNotificationPublisher()
        limiter = FakeLoginRateLimiter()
        service = _service(
            AsyncMock(),
            rate_limiter=limiter,
            publisher=publisher,
            max_resend_attempts=2,
        )
        service._users = repo

        for _ in range(5):
            await service.resend_verification("r@example.com")
        assert len(publisher.calls) == 2  # capped at the throttle limit


# ---------------------------------------------------------------------------
# change password — verify current, rehash, global logout via password_changed_at
# ---------------------------------------------------------------------------


class TestChangePassword:
    async def test_success_rehashes_and_stamps_changed_at(self):
        repo = InMemoryUserRepository()
        user = repo.seed(_user(password="oldpass123"))
        service = _service(AsyncMock())
        service._users = repo

        pair = await service.change_password(user.id, "oldpass123", "newpass456!")

        assert pair.access_token and pair.refresh_token
        stored = await repo.get_by_id(user.id)
        assert PasswordHasher().verify("newpass456!", stored.hashed_password)
        assert stored.token_version == 1  # bumped → old sessions invalidated

    async def test_wrong_current_password_raises(self):
        repo = InMemoryUserRepository()
        user = repo.seed(_user(password="oldpass123"))
        service = _service(AsyncMock())
        service._users = repo

        with pytest.raises(InvalidCredentials):
            await service.change_password(user.id, "wrong", "newpass456!")


# ---------------------------------------------------------------------------
# forgot / reset password
# ---------------------------------------------------------------------------


class TestForgotPassword:
    async def test_sends_reset_for_known_user(self):
        repo = InMemoryUserRepository()
        user = repo.seed(_user(email="u@example.com"))
        publisher = FakeNotificationPublisher()
        service = _service(AsyncMock(), publisher=publisher)
        service._users = repo

        await service.forgot_password("u@example.com")

        assert len(publisher.reset_calls) == 1
        call = publisher.reset_calls[0]
        assert call["user_id"] == str(user.id)
        token = call["reset_url"].split("token=", 1)[1]
        claims = TokenService(settings).decode(token)
        assert claims["type"] == RESET_TOKEN_TYPE
        assert claims["sub"] == str(user.id)

    async def test_silent_for_unknown_email(self):
        publisher = FakeNotificationPublisher()
        service = _service(AsyncMock(), publisher=publisher)
        service._users = InMemoryUserRepository()

        await service.forgot_password("ghost@example.com")
        assert publisher.reset_calls == []

    async def test_throttled_per_address(self):
        repo = InMemoryUserRepository()
        repo.seed(_user(email="u@example.com"))
        publisher = FakeNotificationPublisher()
        service = _service(AsyncMock(), publisher=publisher, max_reset_attempts=2)
        service._users = repo

        for _ in range(5):
            await service.forgot_password("u@example.com")
        assert len(publisher.reset_calls) == 2


class TestResetPassword:
    async def test_valid_token_sets_password_and_revokes(self):
        repo = InMemoryUserRepository()
        user = repo.seed(_user(password="oldpass123"))
        blacklist = FakeBlacklist()
        service = _service(AsyncMock(), blacklist)
        service._users = repo
        token = TokenService(settings).create_reset(str(user.id))

        await service.reset_password(token, "newpass456!")

        stored = await repo.get_by_id(user.id)
        assert PasswordHasher().verify("newpass456!", stored.hashed_password)
        assert stored.token_version == 1  # bumped → old sessions invalidated
        jti = TokenService(settings).decode(token)["jti"]
        assert await blacklist.is_revoked(jti) is True

    async def test_reused_token_raises_revoked(self):
        repo = InMemoryUserRepository()
        user = repo.seed(_user(password="oldpass123"))
        service = _service(AsyncMock(), FakeBlacklist())
        service._users = repo
        token = TokenService(settings).create_reset(str(user.id))

        await service.reset_password(token, "newpass456!")
        with pytest.raises(TokenRevoked):
            await service.reset_password(token, "another789!")

    async def test_access_token_rejected(self):
        repo = InMemoryUserRepository()
        user = repo.seed(_user())
        service = _service(AsyncMock())
        service._users = repo
        access = TokenService(settings).create_access(str(user.id))
        with pytest.raises(TokenInvalid):
            await service.reset_password(access, "newpass456!")

    async def test_unknown_subject_raises_invalid(self):
        service = _service(AsyncMock())
        service._users = InMemoryUserRepository()
        ghost = TokenService(settings).create_reset(str(uuid4()))
        with pytest.raises(TokenInvalid):
            await service.reset_password(ghost, "newpass456!")


# ---------------------------------------------------------------------------
# change username + lookup
# ---------------------------------------------------------------------------


class TestChangeUsername:
    async def test_renames_and_lowercases(self):
        repo = InMemoryUserRepository()
        user = repo.seed(_user(username="old"))
        service = _service(AsyncMock())
        service._users = repo

        result = await service.change_username(user.id, "ReNamed")

        assert result.username == "renamed"
        assert (await repo.get_by_id(user.id)).username == "renamed"

    async def test_duplicate_raises(self):
        repo = InMemoryUserRepository()
        repo.seed(_user(email="a@example.com", username="taken"))
        user = repo.seed(_user(email="b@example.com", username="mine"))
        service = _service(AsyncMock())
        service._users = repo

        with pytest.raises(UsernameTaken):
            await service.change_username(user.id, "taken")


class TestUserLookup:
    async def test_get_user_by_id(self):
        repo = InMemoryUserRepository()
        user = repo.seed(_user(username="bob"))
        service = _service(AsyncMock())
        service._users = repo

        assert (await service.get_user(user.id)).username == "bob"

    async def test_get_user_by_id_missing_raises(self):
        service = _service(AsyncMock())
        service._users = InMemoryUserRepository()
        with pytest.raises(UserNotFound):
            await service.get_user(uuid4())

    async def test_get_user_by_username(self):
        repo = InMemoryUserRepository()
        user = repo.seed(_user(username="bob"))
        service = _service(AsyncMock())
        service._users = repo

        assert (await service.get_user_by_username("bob")).id == user.id

    async def test_get_user_by_username_missing_raises(self):
        service = _service(AsyncMock())
        service._users = InMemoryUserRepository()
        with pytest.raises(UserNotFound):
            await service.get_user_by_username("ghost")


class TestRefreshStaleness:
    async def test_refresh_token_at_old_version_is_revoked(self):
        repo = InMemoryUserRepository()
        user = repo.seed(_user(token_version=1))  # password already changed once
        service = _service(AsyncMock())
        service._users = repo
        # a refresh token minted at the previous version (ver 0)
        now = datetime.now(UTC)
        stale = jwt.encode(
            {
                "sub": str(user.id),
                "jti": uuid4().hex,
                "type": REFRESH_TOKEN_TYPE,
                "ver": 0,
                "iat": now - timedelta(minutes=1),
                "exp": now + timedelta(days=7),
            },
            settings.JWT_SECRET_KEY,
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(TokenRevoked):
            await service.refresh(stale)
