from datetime import datetime

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.chat.model import Conversation, Message
from app.core.chat.repository import ConversationRepository, MessageRepository
from app.infra.database.models import Conversation as ConversationORM
from app.infra.database.models import Message as MessageORM


class SqlAlchemyConversationRepository(ConversationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user_a_id: str, user_b_id: str) -> Conversation:
        orm = ConversationORM(user_a_id=user_a_id, user_b_id=user_b_id)
        self._session.add(orm)
        await self._session.commit()
        await self._session.refresh(orm)
        return self._to_domain(orm)

    async def get_by_id(self, conversation_id: int) -> Conversation | None:
        orm = await self._session.get(ConversationORM, conversation_id)
        return self._to_domain(orm) if orm is not None else None

    async def get_by_pair(self, user_a_id: str, user_b_id: str) -> Conversation | None:
        stmt = select(ConversationORM).where(
            or_(
                (ConversationORM.user_a_id == user_a_id)
                & (ConversationORM.user_b_id == user_b_id),
                (ConversationORM.user_a_id == user_b_id)
                & (ConversationORM.user_b_id == user_a_id),
            )
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return self._to_domain(orm) if orm is not None else None

    async def list_for_user(self, user_id: str) -> list[Conversation]:
        last_activity = (
            select(
                MessageORM.conversation_id,
                func.max(MessageORM.created_at).label("last_at"),
            )
            .group_by(MessageORM.conversation_id)
            .subquery()
        )
        stmt = (
            select(ConversationORM, last_activity.c.last_at)
            .outerjoin(
                last_activity,
                last_activity.c.conversation_id == ConversationORM.id,
            )
            .where(
                or_(
                    ConversationORM.user_a_id == user_id,
                    ConversationORM.user_b_id == user_id,
                )
            )
            .order_by(
                func.coalesce(
                    last_activity.c.last_at, ConversationORM.created_at
                ).desc()
            )
        )
        result = await self._session.execute(stmt)
        return [
            self._to_domain(orm, last_message_at=last_at)
            for orm, last_at in result.all()
        ]

    async def delete(self, conversation_id: int) -> None:
        await self._session.execute(
            sa_delete(MessageORM).where(MessageORM.conversation_id == conversation_id)
        )
        await self._session.execute(
            sa_delete(ConversationORM).where(ConversationORM.id == conversation_id)
        )
        await self._session.commit()

    @staticmethod
    def _to_domain(
        orm: ConversationORM, last_message_at: datetime | None = None
    ) -> Conversation:
        return Conversation(
            id=orm.id,
            user_a_id=orm.user_a_id,
            user_b_id=orm.user_b_id,
            created_at=orm.created_at,
            last_message_at=last_message_at,
        )


class SqlAlchemyMessageRepository(MessageRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, *, conversation_id: int, sender_id: str, content: str
    ) -> Message:
        orm = MessageORM(
            conversation_id=conversation_id, sender_id=sender_id, content=content
        )
        self._session.add(orm)
        await self._session.commit()
        await self._session.refresh(orm)
        return self._to_domain(orm)

    async def list_for_conversation(
        self, *, conversation_id: int, limit: int, offset: int
    ) -> list[Message]:
        stmt = (
            select(MessageORM)
            .where(MessageORM.conversation_id == conversation_id)
            .order_by(MessageORM.created_at.asc(), MessageORM.id.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(orm) for orm in result.scalars().all()]

    @staticmethod
    def _to_domain(orm: MessageORM) -> Message:
        return Message(
            id=orm.id,
            conversation_id=orm.conversation_id,
            sender_id=orm.sender_id,
            content=orm.content,
            created_at=orm.created_at,
        )
