import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.core.auth.exceptions import (
    EmailAlreadyVerified,
    EmailNotVerified,
    InvalidCredentials,
    TokenInvalid,
    TokenRevoked,
    TooManyAttempts,
    UserAlreadyExists,
    UsernameTaken,
    UserNotFound,
)
from app.core.auth.model import User
from app.core.auth.repository import (
    LoginRateLimiter,
    NotificationPublisher,
    TokenBlacklistRepository,
    UserRepository,
)
from app.core.auth.schemas import TokenPair
from app.core.auth.security import (
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
    RESET_TOKEN_TYPE,
    VERIFY_TOKEN_TYPE,
    PasswordHasher,
    TokenService,
)

logger = logging.getLogger(__name__)

# Failed logins allowed per identity before the lockout kicks in (see the
# rate limiter for how long the window lasts).
MAX_LOGIN_ATTEMPTS = 5
# Verification emails allowed per address before resend is silently throttled —
# stops a known address from being mail-bombed via /resend-verification.
MAX_RESEND_ATTEMPTS = 3
# Password-reset emails allowed per address before forgot-password is throttled.
MAX_RESET_ATTEMPTS = 3


class AuthService:
    def __init__(
        self,
        user_repo: UserRepository,
        blacklist: TokenBlacklistRepository,
        tokens: TokenService,
        hasher: PasswordHasher,
        rate_limiter: LoginRateLimiter,
        publisher: NotificationPublisher,
        verify_url_base: str,
        reset_url_base: str,
        max_login_attempts: int = MAX_LOGIN_ATTEMPTS,
        max_resend_attempts: int = MAX_RESEND_ATTEMPTS,
        max_reset_attempts: int = MAX_RESET_ATTEMPTS,
    ) -> None:
        self._users = user_repo
        self._blacklist = blacklist
        self._tokens = tokens
        self._hasher = hasher
        self._rate_limiter = rate_limiter
        self._publisher = publisher
        self._verify_url_base = verify_url_base
        self._reset_url_base = reset_url_base
        self._max_login_attempts = max_login_attempts
        self._max_resend_attempts = max_resend_attempts
        self._max_reset_attempts = max_reset_attempts

    async def register(self, email: str, username: str, password: str) -> User:
        email = email.strip().lower()
        username = username.strip().lower()
        if await self._users.get_by_email(email) is not None:
            raise UserAlreadyExists()
        if await self._users.get_by_username(username) is not None:
            raise UsernameTaken()
        hashed = self._hasher.hash(password)
        user = await self._users.create(email, username, hashed)
        await self._send_verification(user)
        return user

    async def login(self, email: str, password: str) -> TokenPair:
        email = email.strip().lower()
        # Lockout check runs before the DB lookup: a throttled identity costs
        # nothing, and blocking without probing keeps the response identical for
        # existing and unknown emails (no enumeration).
        if await self._rate_limiter.count(email) >= self._max_login_attempts:
            raise TooManyAttempts()
        user = await self._users.get_by_email(email)
        if user is None or not self._hasher.verify(password, user.hashed_password):
            await self._rate_limiter.hit(email)
            raise InvalidCredentials()
        await self._rate_limiter.reset(email)
        # Verified check runs only after the password matched: a wrong password
        # gets the identical InvalidCredentials for known and unknown emails, so
        # the "not verified" signal never leaks to someone without the password.
        if not user.email_verified:
            raise EmailNotVerified()
        return self._issue_pair(str(user.id), user.token_version)

    async def verify_email(self, token: str) -> None:
        claims = self._tokens.decode(token)  # raises TokenExpired / TokenInvalid
        if claims.get("type") != VERIFY_TOKEN_TYPE:
            raise TokenInvalid()
        jti = claims.get("jti")
        # A spent link (jti already revoked) or an already-verified account both
        # mean the confirmation happened — surface the same idempotent error.
        if jti is None or await self._blacklist.is_revoked(jti):
            raise EmailAlreadyVerified()
        user = await self._users.get_by_id(UUID(claims["sub"]))
        if user is None:
            raise TokenInvalid()
        if user.email_verified:
            raise EmailAlreadyVerified()
        await self._users.set_email_verified(user.id)
        await self._revoke(claims)  # single-use: the link can't be replayed

    async def resend_verification(self, email: str) -> None:
        email = email.strip().lower()
        # Always returns the same way regardless of whether the address exists or
        # is already verified (no enumeration); only a real unverified user is
        # actually re-sent to, and only while under the per-address throttle.
        key = f"resend:{email}"
        if await self._rate_limiter.count(key) >= self._max_resend_attempts:
            return
        await self._rate_limiter.hit(key)
        user = await self._users.get_by_email(email)
        if user is None or user.email_verified:
            return
        await self._send_verification(user)

    async def _send_verification(self, user: User) -> None:
        token = self._tokens.create_verify(str(user.id))
        verify_url = f"{self._verify_url_base}?token={token}"
        try:
            await self._publisher.publish_verification(
                user_id=str(user.id), email=user.email, verify_url=verify_url
            )
        except Exception:
            # Best-effort: a down broker must not fail registration — the user
            # can recover via /resend-verification.
            logger.warning("verification email publish failed", exc_info=True)

    async def change_password(
        self, user_id: UUID, current_password: str, new_password: str
    ) -> TokenPair:
        user = await self._users.get_by_id(user_id)
        if user is None or not self._hasher.verify(
            current_password, user.hashed_password
        ):
            raise InvalidCredentials()
        new_version = await self._set_password(user, new_password)
        # Issue the fresh pair at the *new* version so the initiator stays logged
        # in while every token minted at the old version is invalidated.
        return self._issue_pair(str(user_id), new_version)

    async def forgot_password(self, email: str) -> None:
        email = email.strip().lower()
        # Anti-enumeration: always the same outcome; only a real account is
        # actually mailed, and only under the per-address throttle.
        key = f"reset:{email}"
        if await self._rate_limiter.count(key) >= self._max_reset_attempts:
            return
        await self._rate_limiter.hit(key)
        user = await self._users.get_by_email(email)
        if user is None:
            return
        await self._send_password_reset(user)

    async def reset_password(self, token: str, new_password: str) -> None:
        claims = self._tokens.decode(token)  # raises TokenExpired / TokenInvalid
        if claims.get("type") != RESET_TOKEN_TYPE:
            raise TokenInvalid()
        jti = claims.get("jti")
        if jti is None or await self._blacklist.is_revoked(jti):
            raise TokenRevoked()  # spent link
        user = await self._users.get_by_id(UUID(claims["sub"]))
        if user is None:
            raise TokenInvalid()
        await self._set_password(user, new_password)  # bumps version → old sessions die
        await self._revoke(claims)  # single-use

    async def change_username(self, user_id: UUID, username: str) -> User:
        username = username.strip().lower()
        existing = await self._users.get_by_username(username)
        if existing is not None and existing.id != user_id:
            raise UsernameTaken()
        await self._users.update_username(user_id, username)
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFound()
        return user

    async def get_user(self, user_id: UUID) -> User:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFound()
        return user

    async def get_user_by_username(self, username: str) -> User:
        user = await self._users.get_by_username(username.strip().lower())
        if user is None:
            raise UserNotFound()
        return user

    async def _set_password(self, user: User, new_password: str) -> int:
        new_version = user.token_version + 1
        hashed = self._hasher.hash(new_password)
        await self._users.update_password(user.id, hashed, new_version)
        return new_version

    async def _send_password_reset(self, user: User) -> None:
        token = self._tokens.create_reset(str(user.id))
        reset_url = f"{self._reset_url_base}?token={token}"
        try:
            await self._publisher.publish_password_reset(
                user_id=str(user.id), email=user.email, reset_url=reset_url
            )
        except Exception:
            # Best-effort: a down broker must not 500 forgot-password.
            logger.warning("password reset email publish failed", exc_info=True)

    async def refresh(self, refresh_token: str) -> TokenPair:
        claims = self._tokens.decode(refresh_token)
        if claims.get("type") != REFRESH_TOKEN_TYPE:
            raise TokenInvalid()
        jti = claims.get("jti")
        if jti is None or await self._blacklist.is_revoked(jti):
            raise TokenRevoked()
        user = await self._load_subject(claims)  # global-logout after password change
        if user is not None and claims.get("ver", 0) != user.token_version:
            raise TokenRevoked()
        version = user.token_version if user is not None else claims.get("ver", 0)
        await self._revoke(claims)  # rotation: invalidate the presented refresh token
        return self._issue_pair(claims["sub"], version)

    async def _load_subject(self, claims: dict[str, Any]) -> User | None:
        """Load the token's subject, or None if the sub isn't a resolvable user.

        Refresh historically doesn't require the user to still exist (only the
        signature + blacklist matter), so a missing/malformed sub is tolerated —
        the version gate simply doesn't apply.
        """
        sub = claims.get("sub")
        if sub is None:
            return None
        try:
            return await self._users.get_by_id(UUID(sub))
        except ValueError:
            return None

    async def logout(self, refresh_token: str, access_token: str) -> None:
        for token, expected_type in (
            (refresh_token, REFRESH_TOKEN_TYPE),
            (access_token, ACCESS_TOKEN_TYPE),
        ):
            claims = self._tokens.decode(token)
            if claims.get("type") != expected_type:
                raise TokenInvalid()
            await self._revoke(claims)

    def _issue_pair(self, user_id: str, token_version: int = 0) -> TokenPair:
        return TokenPair(
            access_token=self._tokens.create_access(user_id, token_version),
            refresh_token=self._tokens.create_refresh(user_id, token_version),
        )

    async def _revoke(self, claims: dict[str, Any]) -> None:
        jti = claims.get("jti")
        exp = claims.get("exp")
        if jti is None or exp is None:
            return
        ttl = int(exp - datetime.now(UTC).timestamp())
        if ttl > 0:
            await self._blacklist.revoke(jti, ttl)
