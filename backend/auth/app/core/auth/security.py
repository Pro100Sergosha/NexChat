from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import bcrypt
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

from app.core.auth.exceptions import TokenExpired, TokenInvalid
from app.core.config import Settings

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"
VERIFY_TOKEN_TYPE = "verify"
RESET_TOKEN_TYPE = "reset"

# bcrypt hashes at most the first 72 bytes of the input; longer secrets are
# truncated here to avoid the ValueError raised by bcrypt >= 5 on oversized input.
_BCRYPT_MAX_BYTES = 72


class PasswordHasher:
    def hash(self, password: str) -> str:
        secret = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
        return bcrypt.hashpw(secret, bcrypt.gensalt()).decode("utf-8")

    def verify(self, password: str, hashed: str) -> bool:
        secret = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
        try:
            return bcrypt.checkpw(secret, hashed.encode("utf-8"))
        except ValueError:
            # corrupt/foreign hash in the DB column — treat as a failed login,
            # never a 500.
            return False


class TokenService:
    """Mint and verify the four JWT types (access/refresh/verify/reset).

    Every token carries a ``type`` and a unique ``jti``; access/refresh also
    carry a ``ver`` (the user's ``token_version`` at mint time) for global
    logout. Callers must check ``type`` themselves — ``decode`` only validates
    signature and expiry, mapping failures to ``TokenExpired`` / ``TokenInvalid``.
    """

    def __init__(self, settings: Settings) -> None:
        self._secret = settings.JWT_SECRET_KEY
        self._algorithm = settings.jwt_algorithm
        self._access_ttl = timedelta(minutes=settings.jwt_access_token_expire_minutes)
        self._refresh_ttl = timedelta(days=settings.jwt_refresh_token_expire_days)
        self._verify_ttl = timedelta(hours=settings.verify_token_expire_hours)
        self._reset_ttl = timedelta(hours=settings.reset_token_expire_hours)

    def create_access(self, user_id: str, token_version: int = 0) -> str:
        return self._create(user_id, ACCESS_TOKEN_TYPE, self._access_ttl, token_version)

    def create_refresh(self, user_id: str, token_version: int = 0) -> str:
        return self._create(
            user_id, REFRESH_TOKEN_TYPE, self._refresh_ttl, token_version
        )

    def create_verify(self, user_id: str) -> str:
        return self._create(user_id, VERIFY_TOKEN_TYPE, self._verify_ttl)

    def create_reset(self, user_id: str) -> str:
        return self._create(user_id, RESET_TOKEN_TYPE, self._reset_ttl)

    def _create(
        self, user_id: str, token_type: str, ttl: timedelta, token_version: int = 0
    ) -> str:
        now = datetime.now(UTC)
        claims = {
            "sub": user_id,
            "jti": uuid4().hex,
            "type": token_type,
            "ver": token_version,
            "iat": now,
            "exp": now + ttl,
        }
        return jwt.encode(claims, self._secret, algorithm=self._algorithm)

    def decode(self, token: str) -> dict[str, Any]:
        try:
            return jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except ExpiredSignatureError as exc:
            raise TokenExpired() from exc
        except JWTError as exc:
            raise TokenInvalid() from exc
