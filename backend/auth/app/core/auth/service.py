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
        max_login_attempts: int = MAX_LOGIN_ATTEMPTS,
        max_resend_attempts: int = MAX_RESEND_ATTEMPTS,
    ) -> None:
        self._users = user_repo
        self._blacklist = blacklist
        self._tokens = tokens
        self._hasher = hasher
        self._rate_limiter = rate_limiter
        self._publisher = publisher
        self._verify_url_base = verify_url_base
        self._max_login_attempts = max_login_attempts
        self._max_resend_attempts = max_resend_attempts

    async def register(self, email: str, password: str) -> User:
        email = email.strip().lower()
        if await self._users.get_by_email(email) is not None:
            raise UserAlreadyExists()
        hashed = self._hasher.hash(password)
        user = await self._users.create(email, hashed)
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
        return self._issue_pair(str(user.id))

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

    async def refresh(self, refresh_token: str) -> TokenPair:
        claims = self._tokens.decode(refresh_token)
        if claims.get("type") != REFRESH_TOKEN_TYPE:
            raise TokenInvalid()
        jti = claims.get("jti")
        if jti is None or await self._blacklist.is_revoked(jti):
            raise TokenRevoked()
        await self._revoke(claims)  # rotation: invalidate the presented refresh token
        return self._issue_pair(claims["sub"])

    async def logout(self, refresh_token: str, access_token: str) -> None:
        for token, expected_type in (
            (refresh_token, REFRESH_TOKEN_TYPE),
            (access_token, ACCESS_TOKEN_TYPE),
        ):
            claims = self._tokens.decode(token)
            if claims.get("type") != expected_type:
                raise TokenInvalid()
            await self._revoke(claims)

    def _issue_pair(self, user_id: str) -> TokenPair:
        return TokenPair(
            access_token=self._tokens.create_access(user_id),
            refresh_token=self._tokens.create_refresh(user_id),
        )

    async def _revoke(self, claims: dict[str, Any]) -> None:
        jti = claims.get("jti")
        exp = claims.get("exp")
        if jti is None or exp is None:
            return
        ttl = int(exp - datetime.now(UTC).timestamp())
        if ttl > 0:
            await self._blacklist.revoke(jti, ttl)
