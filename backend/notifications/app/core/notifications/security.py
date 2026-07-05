from typing import Any

from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

from app.core.config import Settings
from app.core.notifications.exceptions import TokenExpired, TokenInvalid

ACCESS_TOKEN_TYPE = "access"


class TokenVerifier:
    """Notifications only verifies JWTs issued by auth — it never issues them.

    Same secret + algorithm as auth/chat so the identical access token works
    across every service.
    """

    def __init__(self, settings: Settings) -> None:
        self._secret = settings.JWT_SECRET_KEY
        self._algorithm = settings.jwt_algorithm

    def decode(self, token: str) -> dict[str, Any]:
        try:
            return jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                options={"require_exp": True},
            )
        except ExpiredSignatureError as exc:
            raise TokenExpired() from exc
        except JWTError as exc:
            raise TokenInvalid() from exc

    def verify_access_token(self, token: str) -> str:
        """decode() + the access-token shape rules: type must be "access" and
        sub must be present. Shared by the HTTP dependable and the SSE
        handshake so both enforce the identical rule."""
        claims = self.decode(token)
        if claims.get("type") != ACCESS_TOKEN_TYPE:
            raise TokenInvalid()
        sub = claims.get("sub")
        if sub is None:
            raise TokenInvalid()
        return sub
