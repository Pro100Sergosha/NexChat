"""SqlAlchemyUserRepository against a real (sqlite) session.

Verifies the persistence contract: round-trips, lookups, and the unique
constraint on email actually enforced by the schema.
"""

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.infra.database.repositories import SqlAlchemyUserRepository

# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


async def test_create_returns_populated_user(db_session):
    repo = SqlAlchemyUserRepository(db_session)
    user = await repo.create("new@example.com", "hashed-value")
    assert user.id is not None
    assert user.created_at is not None
    assert user.email == "new@example.com"


async def test_create_persists_hash_verbatim(db_session):
    repo = SqlAlchemyUserRepository(db_session)
    user = await repo.create("new@example.com", "$2b$12$exact-hash-string")
    fetched = await repo.get_by_id(user.id)
    assert fetched is not None
    assert fetched.hashed_password == "$2b$12$exact-hash-string"


async def test_duplicate_email_violates_unique_constraint(db_session):
    repo = SqlAlchemyUserRepository(db_session)
    await repo.create("dupe@example.com", "hash-one")
    with pytest.raises(IntegrityError):
        await repo.create("dupe@example.com", "hash-two")


# ---------------------------------------------------------------------------
# lookups
# ---------------------------------------------------------------------------


async def test_get_by_email_found(db_session):
    repo = SqlAlchemyUserRepository(db_session)
    created = await repo.create("find@example.com", "hash")
    found = await repo.get_by_email("find@example.com")
    assert found is not None
    assert found.id == created.id


async def test_get_by_email_not_found_returns_none(db_session):
    repo = SqlAlchemyUserRepository(db_session)
    assert await repo.get_by_email("ghost@example.com") is None


async def test_get_by_id_found(db_session):
    repo = SqlAlchemyUserRepository(db_session)
    created = await repo.create("find@example.com", "hash")
    found = await repo.get_by_id(created.id)
    assert found is not None
    assert found.email == "find@example.com"


async def test_get_by_id_not_found_returns_none(db_session):
    repo = SqlAlchemyUserRepository(db_session)
    assert await repo.get_by_id(uuid4()) is None


async def test_returned_object_is_domain_entity_not_orm(db_session):
    """The repository maps ORM rows to the frozen domain dataclass."""
    from app.core.auth.model import User

    repo = SqlAlchemyUserRepository(db_session)
    user = await repo.create("domain@example.com", "hash")
    assert type(user) is User
