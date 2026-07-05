from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.exceptions import NotAuthenticated, TokenInvalid, TokenRevoked
from app.core.auth.model import User
from app.core.auth.repository import (
    LoginRateLimiter,
    NotificationPublisher,
    TokenBlacklistRepository,
    UserRepository,
)
from app.core.auth.security import ACCESS_TOKEN_TYPE, PasswordHasher, TokenService
from app.core.auth.service import AuthService
from app.core.config import settings
from app.infra.broker.publisher import RabbitMQPublisher
from app.infra.database.config import get_session
from app.infra.database.repositories import SqlAlchemyUserRepository
from app.infra.redis.blacklist import RedisTokenBlacklist
from app.infra.redis.config import redis_client
from app.infra.redis.rate_limiter import RedisLoginRateLimiter

_password_hasher = PasswordHasher()
_token_service = TokenService(settings)


def get_token_service() -> TokenService:
    return _token_service


def get_password_hasher() -> PasswordHasher:
    return _password_hasher


def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserRepository:
    return SqlAlchemyUserRepository(session)


def get_blacklist() -> TokenBlacklistRepository:
    return RedisTokenBlacklist(redis_client)


def get_rate_limiter() -> LoginRateLimiter:
    return RedisLoginRateLimiter(redis_client)


def get_notification_publisher() -> NotificationPublisher:
    return RabbitMQPublisher(settings)


def get_auth_service(
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    blacklist: Annotated[TokenBlacklistRepository, Depends(get_blacklist)],
    tokens: Annotated[TokenService, Depends(get_token_service)],
    hasher: Annotated[PasswordHasher, Depends(get_password_hasher)],
    rate_limiter: Annotated[LoginRateLimiter, Depends(get_rate_limiter)],
    publisher: Annotated[NotificationPublisher, Depends(get_notification_publisher)],
) -> AuthService:
    return AuthService(
        user_repo,
        blacklist,
        tokens,
        hasher,
        rate_limiter,
        publisher,
        settings.EMAIL_VERIFY_URL_BASE,
    )


# Wired only so Swagger UI renders the "Authorize" button with a password-flow
# login form (posts to tokenUrl, fills the token in automatically). Actual
# token extraction/validation is done by get_access_token below.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login", auto_error=False)


def get_access_token(
    authorization: Annotated[str | None, Header(include_in_schema=False)] = None,
) -> str:
    if authorization is None:
        raise NotAuthenticated()
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise NotAuthenticated()
    return token


async def get_current_user(
    token: Annotated[str, Depends(get_access_token)],
    tokens: Annotated[TokenService, Depends(get_token_service)],
    blacklist: Annotated[TokenBlacklistRepository, Depends(get_blacklist)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> User:
    claims = tokens.decode(token)  # raises TokenExpired / TokenInvalid
    if claims.get("type") != ACCESS_TOKEN_TYPE:
        raise TokenInvalid()
    jti = claims.get("jti")
    if jti is None or await blacklist.is_revoked(jti):
        raise TokenRevoked()
    user = await user_repo.get_by_id(UUID(claims["sub"]))
    if user is None:
        raise TokenInvalid()
    return user
