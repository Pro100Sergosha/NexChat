import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost/")

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient, Response
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from starlette.websockets import WebSocketDisconnect

from app.core.config import settings
from app.infra.database.models import Base, Conversation, Message
from app.infra.redis.connection_manager import ConnectionManager
from app.infra.web.dependables import get_connection_manager, get_db
from app.runner.setup import create_app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


class FakeConnectionManager(ConnectionManager):
    """In-memory stand-in for the Redis-backed connection registry."""

    def __init__(self) -> None:
        self._connections: dict[str, set[int]] = {}

    async def register(self, user_id: str, connection_id: int) -> None:
        self._connections.setdefault(user_id, set()).add(connection_id)

    async def unregister(self, user_id: str, connection_id: int) -> None:
        self._connections.get(user_id, set()).discard(connection_id)

    async def is_online(self, user_id: str) -> bool:
        return bool(self._connections.get(user_id))

    async def connections_for(self, user_id: str) -> set[int]:
        return set(self._connections.get(user_id, set()))


@pytest_asyncio.fixture
async def test_engine():
    """Fresh in-memory SQLite engine + its own StaticPool connection, scoped
    to a single test. Never shared across tests (or across event loops) —
    a session-scoped engine combined with ws_client's real OS-thread portal
    caused cross-test table/connection corruption.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    session_factory = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session


@pytest.fixture
def connection_manager() -> FakeConnectionManager:
    return FakeConnectionManager()


@pytest_asyncio.fixture
async def client(test_engine, db_session, connection_manager):
    session_factory = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_connection_manager] = lambda: connection_manager

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def ws_client(test_engine, db_session, connection_manager):
    """Sync TestClient for WS tests — httpx's ASGITransport has no WS support."""

    session_factory = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_connection_manager] = lambda: connection_manager

    with TestClient(app) as tc:
        yield tc


# ── Factories ────────────────────────────────────────────────────────────────


# TODO: только 1:1 (user_a_id/user_b_id). Групповые диалоги — отдельная
# participants-таблица many-to-many, добавить при появлении требования.
async def make_conversation(
    db: AsyncSession, *, user_a_id: str, user_b_id: str
) -> Conversation:
    conversation = Conversation(user_a_id=user_a_id, user_b_id=user_b_id)
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


# TODO: read_at/is_read поле отложено из MVP — добавить при появлении
# mark-as-read требования.
async def make_message(
    db: AsyncSession, *, conversation_id: int, sender_id: str, content: str
) -> Message:
    message = Message(
        conversation_id=conversation_id, sender_id=sender_id, content=content
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message


def make_token(
    *,
    sub: str = "user-1",
    token_type: str = "access",
    expires_in: int = 900,
    secret: str | None = None,
    algorithm: str | None = None,
) -> str:
    """Craft a JWT directly to control every claim, including expired/forged ones."""
    now = datetime.now(UTC)
    claims = {
        "sub": sub,
        "type": token_type,
        "iat": now - timedelta(seconds=60),
        "exp": now + timedelta(seconds=expires_in),
    }
    return jwt.encode(
        claims,
        secret if secret is not None else settings.JWT_SECRET_KEY,
        algorithm=algorithm or settings.jwt_algorithm,
    )


def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def assert_error(resp: Response, status: int, code: str) -> None:
    """Every error response must carry a stable code and a human-readable message."""
    assert resp.status_code == status, (
        f"expected {status}, got {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    assert body.get("code") == code, f"expected code={code!r}, got body={body!r}"
    message = body.get("message")
    assert isinstance(message, str) and message.strip(), f"empty message: {body!r}"
    assert message != code, "message must not just repeat the code"
    assert " " in message, f"message must be human-readable prose, got {message!r}"


def assert_ws_close(client: TestClient, url: str, code: int) -> None:
    """WS handshake rejection: server closes before/at accept, so entering the
    connect context manager itself raises WebSocketDisconnect with the code."""
    with pytest.raises(WebSocketDisconnect) as exc_info, client.websocket_connect(url):
        pass
    assert exc_info.value.code == code, (
        f"expected close code {code}, got {exc_info.value.code}"
    )
