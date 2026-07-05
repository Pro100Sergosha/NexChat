from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.chat.exceptions import NotAuthenticated
from app.core.chat.repository import (
    ConversationRepository,
    MessageRepository,
    NotificationPublisher,
)
from app.core.chat.security import TokenVerifier
from app.core.chat.service import ChatService
from app.core.config import settings
from app.infra.broker.publisher import RabbitMQPublisher
from app.infra.database.config import async_session_factory
from app.infra.database.repositories import (
    SqlAlchemyConversationRepository,
    SqlAlchemyMessageRepository,
)
from app.infra.redis.config import redis_client
from app.infra.redis.connection_manager import ConnectionManager, RedisConnectionManager

_token_verifier = TokenVerifier(settings)
_connection_manager = RedisConnectionManager(redis_client)
# Single long-lived publisher: its connection is opened once at startup and
# closed at shutdown by the app lifespan (see runner/setup.py).
_notification_publisher = RabbitMQPublisher(settings.RABBITMQ_URL)


async def get_db():
    async with async_session_factory() as session:
        yield session


def get_token_verifier() -> TokenVerifier:
    return _token_verifier


def get_connection_manager() -> ConnectionManager:
    return _connection_manager


def get_notification_publisher() -> NotificationPublisher:
    return _notification_publisher


def get_access_token(
    authorization: Annotated[str | None, Header(include_in_schema=False)] = None,
) -> str:
    if authorization is None:
        raise NotAuthenticated()
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise NotAuthenticated()
    return token


async def get_current_user_id(
    token: Annotated[str, Depends(get_access_token)],
    verifier: Annotated[TokenVerifier, Depends(get_token_verifier)],
) -> str:
    return verifier.verify_access_token(token)


def get_conversation_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ConversationRepository:
    return SqlAlchemyConversationRepository(session)


def get_message_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MessageRepository:
    return SqlAlchemyMessageRepository(session)


def get_chat_service(
    conversation_repo: Annotated[
        ConversationRepository, Depends(get_conversation_repository)
    ],
    message_repo: Annotated[MessageRepository, Depends(get_message_repository)],
    publisher: Annotated[NotificationPublisher, Depends(get_notification_publisher)],
) -> ChatService:
    return ChatService(
        conversation_repo=conversation_repo,
        message_repo=message_repo,
        publisher=publisher,
    )
