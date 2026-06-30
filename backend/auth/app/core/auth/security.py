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

# bcrypt hashes at most the first 72 bytes of the input; longer secrets are
# truncated here to avoid the ValueError raised by bcrypt >= 5 on oversized input.
_BCRYPT_MAX_BYTES = 72


class PasswordHasher:
    def hash(self, password: str) -> str:
        secret = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
        return bcrypt.hashpw(secret, bcrypt.gensalt()).decode("utf-8")

    def verify(self, password: str, hashed: str) -> bool:
        secret = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
        return bcrypt.checkpw(secret, hashed.encode("utf-8"))


class TokenService:
    def __init__(self, settings: Settings) -> None:
        self._secret = settings.JWT_SECRET_KEY
        self._algorithm = settings.jwt_algorithm
        self._access_ttl = timedelta(minutes=settings.jwt_access_token_expire_minutes)
        self._refresh_ttl = timedelta(days=settings.jwt_refresh_token_expire_days)

    def create_access(self, user_id: str) -> str:
        return self._create(user_id, ACCESS_TOKEN_TYPE, self._access_ttl)

    def create_refresh(self, user_id: str) -> str:
        return self._create(user_id, REFRESH_TOKEN_TYPE, self._refresh_ttl)

    def _create(self, user_id: str, token_type: str, ttl: timedelta) -> str:
        now = datetime.now(UTC)
        claims = {
            "sub": user_id,
            "jti": uuid4().hex,
            "type": token_type,
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
