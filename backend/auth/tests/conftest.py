import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient, Response
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.auth.model import User
from app.core.auth.repository import TokenBlacklistRepository, UserRepository
from app.core.auth.security import PasswordHasher, TokenService
from app.core.config import settings
from app.infra.database.base import Base
from app.infra.database.config import get_session
from app.infra.database.models import UserORM
from app.infra.web.dependables import get_blacklist
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


class InMemoryUserRepository(UserRepository):
    """Dict-backed UserRepository for tests that don't need a real session."""

    def __init__(self) -> None:
        self._by_id: dict[UUID, User] = {}

    def seed(self, user: User) -> User:
        self._by_id[user.id] = user
        return user

    async def get_by_email(self, email: str) -> User | None:
        return next(
            (u for u in self._by_id.values() if u.email == email), None
        )

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self._by_id.get(user_id)

    async def create(self, email: str, hashed_password: str) -> User:
        user = User(
            id=uuid4(),
            email=email,
            hashed_password=hashed_password,
            created_at=datetime.now(UTC),
        )
        return self.seed(user)


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


@pytest_asyncio.fixture
async def client(db_session):
    _blacklist = FakeBlacklist()

    async def override_get_session():
        yield db_session

    def override_blacklist():
        return _blacklist

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_blacklist] = override_blacklist

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, db_session, _blacklist


# ── Factories ────────────────────────────────────────────────────────────────


async def make_user(
    db: AsyncSession,
    *,
    email: str = "user@example.com",
    password: str = "password123",
) -> tuple[User, str]:
    """Insert a user with a real bcrypt hash; return (user, plaintext_password)."""
    orm = UserORM(id=uuid4(), email=email, hashed_password=PasswordHasher().hash(password))
    db.add(orm)
    await db.commit()
    await db.refresh(orm)
    user = User(
        id=orm.id,
        email=orm.email,
        hashed_password=orm.hashed_password,
        created_at=orm.created_at,
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
    assert resp.status_code == status, f"expected {status}, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body.get("code") == code, f"expected code={code!r}, got body={body!r}"
    message = body.get("message")
    assert isinstance(message, str) and message.strip(), f"empty message: {body!r}"
    assert message != code, "message must not just repeat the code"
    assert " " in message, f"message must be human-readable prose, got {message!r}"
