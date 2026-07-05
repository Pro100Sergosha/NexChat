from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.model import User
from app.core.auth.repository import UserRepository
from app.infra.database.models import UserORM


class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(UserORM).where(UserORM.email == email)
        )
        orm = result.scalar_one_or_none()
        return self._to_domain(orm) if orm is not None else None

    async def get_by_username(self, username: str) -> User | None:
        result = await self._session.execute(
            select(UserORM).where(UserORM.username == username)
        )
        orm = result.scalar_one_or_none()
        return self._to_domain(orm) if orm is not None else None

    async def get_by_id(self, user_id: UUID) -> User | None:
        orm = await self._session.get(UserORM, user_id)
        return self._to_domain(orm) if orm is not None else None

    async def create(self, email: str, username: str, hashed_password: str) -> User:
        orm = UserORM(email=email, username=username, hashed_password=hashed_password)
        self._session.add(orm)
        await self._session.commit()
        await self._session.refresh(orm)
        return self._to_domain(orm)

    async def set_email_verified(self, user_id: UUID) -> None:
        orm = await self._session.get(UserORM, user_id)
        if orm is None:
            return
        orm.email_verified = True
        await self._session.commit()

    async def update_username(self, user_id: UUID, username: str) -> None:
        orm = await self._session.get(UserORM, user_id)
        if orm is None:
            return
        orm.username = username
        await self._session.commit()

    async def update_password(
        self, user_id: UUID, hashed_password: str, token_version: int
    ) -> None:
        orm = await self._session.get(UserORM, user_id)
        if orm is None:
            return
        orm.hashed_password = hashed_password
        orm.token_version = token_version
        await self._session.commit()

    @staticmethod
    def _to_domain(orm: UserORM) -> User:
        return User(
            id=orm.id,
            email=orm.email,
            username=orm.username,
            hashed_password=orm.hashed_password,
            created_at=orm.created_at,
            email_verified=orm.email_verified,
            token_version=orm.token_version,
        )
