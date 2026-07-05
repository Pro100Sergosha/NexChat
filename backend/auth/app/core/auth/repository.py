from abc import ABC, abstractmethod
from uuid import UUID

from app.core.auth.model import User


class UserRepository(ABC):
    @abstractmethod
    async def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    async def get_by_username(self, username: str) -> User | None: ...

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> User | None: ...

    @abstractmethod
    async def create(self, email: str, username: str, hashed_password: str) -> User: ...

    @abstractmethod
    async def set_email_verified(self, user_id: UUID) -> None: ...

    @abstractmethod
    async def update_username(self, user_id: UUID, username: str) -> None: ...

    @abstractmethod
    async def update_password(
        self, user_id: UUID, hashed_password: str, token_version: int
    ) -> None: ...


class NotificationPublisher(ABC):
    """Port for handing a transactional email off to the notifications service.

    Domain-shaped on purpose: the service asks for a *verification* or *password
    reset* email, not a generic broker event — the wire/broker format is an infra
    concern.
    """

    @abstractmethod
    async def publish_verification(
        self, *, user_id: str, email: str, verify_url: str
    ) -> None: ...

    @abstractmethod
    async def publish_password_reset(
        self, *, user_id: str, email: str, reset_url: str
    ) -> None: ...


class TokenBlacklistRepository(ABC):
    @abstractmethod
    async def revoke(self, jti: str, ttl_seconds: int) -> None: ...

    @abstractmethod
    async def is_revoked(self, jti: str) -> bool: ...


class LoginRateLimiter(ABC):
    @abstractmethod
    async def hit(self, identity: str) -> int: ...

    @abstractmethod
    async def count(self, identity: str) -> int: ...

    @abstractmethod
    async def reset(self, identity: str) -> None: ...
