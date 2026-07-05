import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("SERVICE_TOKEN", "test-service-token")

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient, Response
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.notifications.model import DeviceToken, Notification
from app.core.notifications.repository import (
    EmailSender,
    EventBus,
    NotificationBroker,
    Presence,
    PushSender,
)
from app.core.notifications.schemas import NotificationEvent
from app.core.notifications.service import NotificationService
from app.infra.database.base import Base
from app.infra.database.config import get_session
from app.infra.database.repositories import (
    SqlAlchemyDeviceTokenRepository,
    SqlAlchemyNotificationRepository,
)
from app.infra.web.dependables import (
    get_broker,
    get_email,
    get_event_bus,
    get_presence,
    get_push,
)
from app.runner.setup import create_app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)


# ── Fakes ─────────────────────────────────────────────────────────────────────


class FakePresence(Presence):
    """In-memory presence set per user; toggle online with set_online()."""

    def __init__(self) -> None:
        self._conns: dict[str, set[int]] = defaultdict(set)

    def set_online(self, user_id: str, *, online: bool = True) -> None:
        if online:
            self._conns[user_id].add(1)
        else:
            self._conns.pop(user_id, None)

    async def register(self, user_id: str, connection_id: int) -> None:
        self._conns[user_id].add(connection_id)

    async def unregister(self, user_id: str, connection_id: int) -> None:
        self._conns[user_id].discard(connection_id)

    async def is_online(self, user_id: str) -> bool:
        return bool(self._conns.get(user_id))


class FakeEventBus(EventBus):
    """asyncio.Queue-backed pub/sub — publish fans out to live subscribers."""

    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []
        self._subscribers: dict[str, list[asyncio.Queue[str]]] = defaultdict(list)

    async def publish(self, user_id: str, payload: str) -> None:
        self.published.append((user_id, payload))
        for queue in self._subscribers.get(user_id, []):
            queue.put_nowait(payload)

    async def subscribe(self, user_id: str) -> AsyncIterator[str]:
        queue: asyncio.Queue[str] = asyncio.Queue()
        self._subscribers[user_id].append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers[user_id].remove(queue)


class FakePush(PushSender):
    """Records sends; returns a configurable set of 'invalid' tokens to prune."""

    def __init__(self) -> None:
        self.sent: list[tuple[list[DeviceToken], Notification]] = []
        self.invalid_tokens: set[str] = set()

    async def send(
        self, tokens: list[DeviceToken], notification: Notification
    ) -> set[str]:
        self.sent.append((tokens, notification))
        return {t.token for t in tokens if t.token in self.invalid_tokens}


class FakeEmail(EmailSender):
    """Records email sends over the forced-email channel."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, Notification]] = []

    async def send(self, address: str, notification: Notification) -> None:
        self.sent.append((address, notification))


class FakeBroker(NotificationBroker):
    """Runs the registered pipeline handler synchronously on publish, so an
    end-to-end POST persists + routes without a real RabbitMQ/consumer."""

    def __init__(self) -> None:
        self.published: list[NotificationEvent] = []
        self._handler = None

    def set_handler(self, handler) -> None:
        self._handler = handler

    async def publish(self, event: NotificationEvent) -> None:
        self.published.append(event)
        if self._handler is not None:
            await self._handler(event)

    async def run_consumer(self, handler) -> None:
        self.set_handler(handler)


@dataclass
class Fakes:
    presence: FakePresence
    event_bus: FakeEventBus
    push: FakePush
    email: FakeEmail
    broker: FakeBroker


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_session():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestingSessionLocal() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def fakes() -> Fakes:
    return Fakes(FakePresence(), FakeEventBus(), FakePush(), FakeEmail(), FakeBroker())


@pytest_asyncio.fixture
async def client(db_session, fakes):
    async def override_get_session():
        yield db_session

    def override_presence():
        return fakes.presence

    def override_event_bus():
        return fakes.event_bus

    def override_push():
        return fakes.push

    def override_email():
        return fakes.email

    def override_broker():
        return fakes.broker

    # The broker's handler is the emit pipeline over the test session.
    async def pipeline(event: NotificationEvent) -> None:
        service = NotificationService(
            notifications=SqlAlchemyNotificationRepository(db_session),
            device_tokens=SqlAlchemyDeviceTokenRepository(db_session),
            presence=fakes.presence,
            event_bus=fakes.event_bus,
            push=fakes.push,
            email=fakes.email,
        )
        await service.emit(event)

    fakes.broker.set_handler(pipeline)

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_presence] = override_presence
    app.dependency_overrides[get_event_bus] = override_event_bus
    app.dependency_overrides[get_push] = override_push
    app.dependency_overrides[get_email] = override_email
    app.dependency_overrides[get_broker] = override_broker

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, db_session, fakes


@pytest.fixture
def service(db_session, fakes) -> NotificationService:
    """Service wired to the real sqlite repos + fakes, for unit/integration use."""
    return NotificationService(
        notifications=SqlAlchemyNotificationRepository(db_session),
        device_tokens=SqlAlchemyDeviceTokenRepository(db_session),
        presence=fakes.presence,
        event_bus=fakes.event_bus,
        push=fakes.push,
        email=fakes.email,
    )


# ── Factories / helpers ─────────────────────────────────────────────────────────


def make_token(
    *,
    sub: str = "user-1",
    token_type: str = "access",
    expires_in: int = 900,
    secret: str | None = None,
) -> str:
    """Craft a JWT directly to control every claim (incl. expired/forged)."""
    now = datetime.now(UTC)
    claims = {
        "sub": sub,
        "jti": uuid4().hex,
        "type": token_type,
        "iat": now - timedelta(seconds=60),
        "exp": now + timedelta(seconds=expires_in),
    }
    return jwt.encode(
        claims, secret or settings.JWT_SECRET_KEY, algorithm=settings.jwt_algorithm
    )


def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def service_headers() -> dict[str, str]:
    """Trusted-producer header for POST /notifications (matches conftest env)."""
    return {"X-Service-Token": "test-service-token"}


async def make_notification(
    db: AsyncSession,
    *,
    user_id: str = "user-1",
    type: str = "message",
    title: str = "New message",
    body: str = "hello",
    data: dict | None = None,
) -> Notification:
    repo = SqlAlchemyNotificationRepository(db)
    return await repo.create(
        user_id=user_id, type=type, title=title, body=body, data=data or {}
    )


async def make_device(
    db: AsyncSession,
    *,
    user_id: str = "user-1",
    token: str = "device-token-1",
    platform: str = "web",
) -> DeviceToken:
    repo = SqlAlchemyDeviceTokenRepository(db)
    return await repo.add(user_id=user_id, token=token, platform=platform)


def assert_error(resp: Response, status: int, code: str) -> None:
    assert resp.status_code == status, (
        f"expected {status}, got {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    assert body.get("code") == code, f"expected code={code!r}, got body={body!r}"
    message = body.get("message")
    assert isinstance(message, str) and message.strip(), f"empty message: {body!r}"
    assert message != code, "message must not just repeat the code"
    assert " " in message, f"message must be human-readable prose, got {message!r}"
