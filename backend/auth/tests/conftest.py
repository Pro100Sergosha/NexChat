import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient, Response
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.auth.model import User
from app.core.auth.repository import (
    LoginRateLimiter,
    NotificationPublisher,
    TokenBlacklistRepository,
    UserRepository,
)
from app.core.auth.security import PasswordHasher, TokenService
from app.core.config import settings
from app.infra.database.base import Base
from app.infra.database.config import get_session
from app.infra.database.models import UserORM
from app.infra.web.dependables import (
    get_blacklist,
    get_notification_publisher,
    get_rate_limiter,
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


class FakeBlacklist(TokenBlacklistRepository):
    """In-memory stand-in for Redis blacklist — jti kept until test ends."""

    def __init__(self) -> None:
        self._store: dict[str, int] = {}

    async def revoke(self, jti: str, ttl_seconds: int) -> None:
        self._store[jti] = ttl_seconds

    async def is_revoked(self, jti: str) -> bool:
        return jti in self._store


class FakeLoginRateLimiter(LoginRateLimiter):
    """In-memory stand-in for the Redis failed-login counter (no TTL expiry)."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    async def hit(self, identity: str) -> int:
        self._counts[identity] = self._counts.get(identity, 0) + 1
        return self._counts[identity]

    async def count(self, identity: str) -> int:
        return self._counts.get(identity, 0)

    async def reset(self, identity: str) -> None:
        self._counts.pop(identity, None)


class InMemoryUserRepository(UserRepository):
    """Dict-backed UserRepository for tests that don't need a real session."""

    def __init__(self) -> None:
        self._by_id: dict[UUID, User] = {}

    def seed(self, user: User) -> User:
        self._by_id[user.id] = user
        return user

    async def get_by_email(self, email: str) -> User | None:
        return next((u for u in self._by_id.values() if u.email == email), None)

    async def get_by_username(self, username: str) -> User | None:
        return next((u for u in self._by_id.values() if u.username == username), None)

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self._by_id.get(user_id)

    async def create(self, email: str, username: str, hashed_password: str) -> User:
        user = User(
            id=uuid4(),
            email=email,
            username=username,
            hashed_password=hashed_password,
            created_at=datetime.now(UTC),
            email_verified=False,
            token_version=0,
        )
        return self.seed(user)

    async def set_email_verified(self, user_id: UUID) -> None:
        user = self._by_id.get(user_id)
        if user is not None:
            self._by_id[user_id] = replace(user, email_verified=True)

    async def update_username(self, user_id: UUID, username: str) -> None:
        user = self._by_id.get(user_id)
        if user is not None:
            self._by_id[user_id] = replace(user, username=username)

    async def update_password(
        self, user_id: UUID, hashed_password: str, token_version: int
    ) -> None:
        user = self._by_id.get(user_id)
        if user is not None:
            self._by_id[user_id] = replace(
                user,
                hashed_password=hashed_password,
                token_version=token_version,
            )


class FakeNotificationPublisher(NotificationPublisher):
    """Records each transactional-email publish so tests can assert on it."""

    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []
        self.reset_calls: list[dict[str, str]] = []

    async def publish_verification(
        self, *, user_id: str, email: str, verify_url: str
    ) -> None:
        self.calls.append(
            {"user_id": user_id, "email": email, "verify_url": verify_url}
        )

    async def publish_password_reset(
        self, *, user_id: str, email: str, reset_url: str
    ) -> None:
        self.reset_calls.append(
            {"user_id": user_id, "email": email, "reset_url": reset_url}
        )


@pytest.fixture
def hasher() -> PasswordHasher:
    return PasswordHasher()


@pytest.fixture
def tokens() -> TokenService:
    return TokenService(settings)


@pytest_asyncio.fixture
async def db_session():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestingSessionLocal() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def publisher() -> "FakeNotificationPublisher":
    """The verification-email spy wired into the ``client`` app (same instance)."""
    return FakeNotificationPublisher()


@pytest_asyncio.fixture
async def client(db_session, publisher):
    _blacklist = FakeBlacklist()
    _rate_limiter = FakeLoginRateLimiter()

    async def override_get_session():
        yield db_session

    def override_blacklist():
        return _blacklist

    def override_rate_limiter():
        return _rate_limiter

    def override_publisher():
        return publisher

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_blacklist] = override_blacklist
    app.dependency_overrides[get_rate_limiter] = override_rate_limiter
    app.dependency_overrides[get_notification_publisher] = override_publisher

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, db_session, _blacklist


# ── Factories ────────────────────────────────────────────────────────────────


async def make_user(
    db: AsyncSession,
    *,
    email: str = "user@example.com",
    username: str | None = None,
    password: str = "password123",
    email_verified: bool = True,
    token_version: int = 0,
) -> tuple[User, str]:
    """Insert a user with a real bcrypt hash; return (user, plaintext_password).

    Defaults to verified so login-centric tests aren't blocked by the email gate;
    pass ``email_verified=False`` to exercise the unverified path. ``username``
    defaults to a unique ``user_<hex>`` so callers that don't care never collide.
    """
    orm = UserORM(
        id=uuid4(),
        email=email,
        username=username or f"user_{uuid4().hex[:8]}",
        hashed_password=PasswordHasher().hash(password),
        email_verified=email_verified,
        token_version=token_version,
    )
    db.add(orm)
    await db.commit()
    await db.refresh(orm)
    user = User(
        id=orm.id,
        email=orm.email,
        username=orm.username,
        hashed_password=orm.hashed_password,
        created_at=orm.created_at,
        email_verified=orm.email_verified,
        token_version=orm.token_version,
    )
    return user, password


def make_token(
    *,
    sub: str = "user-1",
    token_type: str = "access",
    expires_in: int = 900,
    jti: str | None = None,
    secret: str | None = None,
) -> str:
    """Craft a JWT directly (bypassing TokenService) to control every claim.

    ``expires_in`` may be negative to produce an already-expired token.
    """
    now = datetime.now(UTC)
    claims = {
        "sub": sub,
        "jti": jti or uuid4().hex,
        "type": token_type,
        "iat": now - timedelta(seconds=60),
        "exp": now + timedelta(seconds=expires_in),
    }
    return jwt.encode(
        claims, secret or settings.JWT_SECRET_KEY, algorithm=settings.jwt_algorithm
    )


# ── API helpers ──────────────────────────────────────────────────────────────


def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def login_tokens(
    ac: AsyncClient,
    db: AsyncSession,
    *,
    email: str = "user@example.com",
    password: str = "password123",
) -> dict:
    """Create a user and log in through the API (OAuth2 form); return token pair."""
    await make_user(db, email=email, password=password)
    resp = await ac.post("/login", data={"username": email, "password": password})
    assert resp.status_code == 200, f"login failed: {resp.status_code} {resp.text}"
    return resp.json()


def assert_error(resp: Response, status: int, code: str) -> None:
    """Every error response must carry a stable code and a human-readable message.

    The message must be an actual sentence (contains spaces), never a bare
    class name like ``InvalidCredentials`` and never empty.
    """
    assert resp.status_code == status, (
        f"expected {status}, got {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    assert body.get("code") == code, f"expected code={code!r}, got body={body!r}"
    message = body.get("message")
    assert isinstance(message, str) and message.strip(), f"empty message: {body!r}"
    assert message != code, "message must not just repeat the code"
    assert " " in message, f"message must be human-readable prose, got {message!r}"
