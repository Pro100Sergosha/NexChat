from datetime import UTC, datetime
from typing import Any

from app.core.auth.exceptions import (
    InvalidCredentials,
    TokenInvalid,
    TokenRevoked,
    UserAlreadyExists,
)
from app.core.auth.model import User
from app.core.auth.repository import TokenBlacklistRepository, UserRepository
from app.core.auth.schemas import TokenPair
from app.core.auth.security import (
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
    PasswordHasher,
    TokenService,
)


class AuthService:
    def __init__(
        self,
        user_repo: UserRepository,
        blacklist: TokenBlacklistRepository,
        tokens: TokenService,
        hasher: PasswordHasher,
    ) -> None:
        self._users = user_repo
        self._blacklist = blacklist
        self._tokens = tokens
        self._hasher = hasher

    async def register(self, email: str, password: str) -> User:
        if await self._users.get_by_email(email) is not None:
            raise UserAlreadyExists(email)
        hashed = self._hasher.hash(password)
        return await self._users.create(email, hashed)

    async def login(self, email: str, password: str) -> TokenPair:
        user = await self._users.get_by_email(email)
        if user is None or not self._hasher.verify(password, user.hashed_password):
            raise InvalidCredentials()
        return self._issue_pair(str(user.id))

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
