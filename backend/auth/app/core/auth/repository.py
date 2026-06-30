from abc import ABC, abstractmethod
from uuid import UUID

from app.core.auth.model import User


class UserRepository(ABC):
    @abstractmethod
    async def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> User | None: ...

    @abstractmethod
    async def create(self, email: str, hashed_password: str) -> User: ...


class TokenBlacklistRepository(ABC):
    @abstractmethod
    async def revoke(self, jti: str, ttl_seconds: int) -> None: ...

    @abstractmethod
    async def is_revoked(self, jti: str) -> bool: ...
