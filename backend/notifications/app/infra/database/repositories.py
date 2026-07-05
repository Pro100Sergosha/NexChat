from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.notifications.model import DeviceToken, Notification
from app.core.notifications.repository import (
    DeviceTokenRepository,
    NotificationRepository,
)
from app.infra.database.models import DeviceTokenORM, NotificationORM


class SqlAlchemyNotificationRepository(NotificationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: str,
        type: str,
        title: str,
        body: str,
        data: dict[str, Any],
    ) -> Notification:
        orm = NotificationORM(
            user_id=user_id, type=type, title=title, body=body, data=data
        )
        self._session.add(orm)
        await self._session.commit()
        await self._session.refresh(orm)
        return self._to_domain(orm)

    async def get_by_id(self, notification_id: UUID) -> Notification | None:
        orm = await self._session.get(NotificationORM, notification_id)
        return self._to_domain(orm) if orm is not None else None

    async def list_for_user(self, user_id: str) -> list[Notification]:
        result = await self._session.execute(
            select(NotificationORM)
            .where(NotificationORM.user_id == user_id)
            .order_by(NotificationORM.created_at.desc())
        )
        return [self._to_domain(orm) for orm in result.scalars().all()]

    async def mark_read(self, notification_id: UUID) -> None:
        orm = await self._session.get(NotificationORM, notification_id)
        if orm is None:
            return
        orm.read = True
        await self._session.commit()

    @staticmethod
    def _to_domain(orm: NotificationORM) -> Notification:
        return Notification(
            id=orm.id,
            user_id=orm.user_id,
            type=orm.type,
            title=orm.title,
            body=orm.body,
            data=orm.data,
            read=orm.read,
            created_at=orm.created_at,
        )


class SqlAlchemyDeviceTokenRepository(DeviceTokenRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, *, user_id: str, token: str, platform: str) -> DeviceToken:
        orm = DeviceTokenORM(user_id=user_id, token=token, platform=platform)
        self._session.add(orm)
        await self._session.commit()
        await self._session.refresh(orm)
        return self._to_domain(orm)

    async def get_by_token(self, token: str) -> DeviceToken | None:
        result = await self._session.execute(
            select(DeviceTokenORM).where(DeviceTokenORM.token == token)
        )
        orm = result.scalar_one_or_none()
        return self._to_domain(orm) if orm is not None else None

    async def list_for_user(self, user_id: str) -> list[DeviceToken]:
        result = await self._session.execute(
            select(DeviceTokenORM).where(DeviceTokenORM.user_id == user_id)
        )
        return [self._to_domain(orm) for orm in result.scalars().all()]

    async def remove(self, token: str) -> None:
        await self._session.execute(
            delete(DeviceTokenORM).where(DeviceTokenORM.token == token)
        )
        await self._session.commit()

    async def delete_many(self, tokens: set[str]) -> None:
        if not tokens:
            return
        await self._session.execute(
            delete(DeviceTokenORM).where(DeviceTokenORM.token.in_(tokens))
        )
        await self._session.commit()

    @staticmethod
    def _to_domain(orm: DeviceTokenORM) -> DeviceToken:
        return DeviceToken(
            id=orm.id,
            user_id=orm.user_id,
            token=orm.token,
            platform=orm.platform,
            created_at=orm.created_at,
        )
