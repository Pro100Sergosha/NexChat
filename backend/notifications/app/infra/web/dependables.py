import secrets
from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.notifications.exceptions import NotAuthenticated, NotAuthorized
from app.core.notifications.repository import (
    DeviceTokenRepository,
    EmailSender,
    EventBus,
    NotificationBroker,
    NotificationRepository,
    Presence,
    PushSender,
)
from app.core.notifications.security import TokenVerifier
from app.core.notifications.service import NotificationService
from app.infra.database.config import get_session
from app.infra.database.repositories import (
    SqlAlchemyDeviceTokenRepository,
    SqlAlchemyNotificationRepository,
)
from app.infra.redis.config import redis_client
from app.infra.redis.presence import RedisPresence
from app.infra.redis.pubsub import RedisEventBus

_token_verifier = TokenVerifier(settings)
_presence = RedisPresence(redis_client)
_event_bus = RedisEventBus(redis_client)


def get_token_verifier() -> TokenVerifier:
    return _token_verifier


def get_presence() -> Presence:
    return _presence


def get_event_bus() -> EventBus:
    return _event_bus


def get_push() -> PushSender:
    # Lazy import: firebase-admin is only needed for the real offline path.
    # Tests inject a FakePush and never import it.
    from app.infra.fcm.client import FirebasePushSender

    return FirebasePushSender(settings)


def get_email() -> EmailSender:
    # Lazy import: aiosmtplib is only needed for the real email channel.
    # Tests inject a FakeEmail and never import it.
    from app.infra.email.client import SmtpEmailSender

    return SmtpEmailSender(settings)


def get_broker() -> NotificationBroker:
    # Lazy import: aio-pika is only needed when actually talking to RabbitMQ.
    from app.infra.broker.broker import RabbitMQBroker

    return RabbitMQBroker(settings)


def get_notification_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NotificationRepository:
    return SqlAlchemyNotificationRepository(session)


def get_device_token_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DeviceTokenRepository:
    return SqlAlchemyDeviceTokenRepository(session)


def get_notification_service(
    notifications: Annotated[
        NotificationRepository, Depends(get_notification_repository)
    ],
    device_tokens: Annotated[
        DeviceTokenRepository, Depends(get_device_token_repository)
    ],
    presence: Annotated[Presence, Depends(get_presence)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
    push: Annotated[PushSender, Depends(get_push)],
    email: Annotated[EmailSender, Depends(get_email)],
) -> NotificationService:
    return NotificationService(
        notifications=notifications,
        device_tokens=device_tokens,
        presence=presence,
        event_bus=event_bus,
        push=push,
        email=email,
    )


# Wired only so Swagger renders the "Authorize" button; the auth service issues
# the token. Extraction/validation is done by get_access_token below.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_access_token(
    authorization: Annotated[str | None, Header(include_in_schema=False)] = None,
) -> str:
    if authorization is None:
        raise NotAuthenticated()
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise NotAuthenticated()
    return token


def get_current_user_id(
    token: Annotated[str, Depends(get_access_token)],
    verifier: Annotated[TokenVerifier, Depends(get_token_verifier)],
) -> str:
    return verifier.verify_access_token(token)  # raises TokenExpired/TokenInvalid


def require_service_token(
    x_service_token: Annotated[str | None, Header(include_in_schema=False)] = None,
) -> None:
    """Gate the producer-facing emit endpoint. A user JWT is the wrong auth here
    (the recipient is an arbitrary user_id, not the caller) — spoofing that was
    the IDOR. Trusted producers present X-Service-Token instead; constant-time
    compared. Unset SERVICE_TOKEN disables the path entirely."""
    expected = settings.SERVICE_TOKEN
    if (
        not expected
        or x_service_token is None
        or not secrets.compare_digest(x_service_token, expected)
    ):
        raise NotAuthorized()
