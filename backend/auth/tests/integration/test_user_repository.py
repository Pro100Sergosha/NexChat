"""SqlAlchemyUserRepository against a real (sqlite) session.

Verifies the persistence contract: round-trips, lookups, and the unique
constraints on email and username actually enforced by the schema.
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
    user = await repo.create("new@example.com", "newbie", "hashed-value")
    assert user.id is not None
    assert user.created_at is not None
    assert user.email == "new@example.com"
    assert user.username == "newbie"
    assert user.token_version == 0


async def test_create_persists_hash_verbatim(db_session):
    repo = SqlAlchemyUserRepository(db_session)
    user = await repo.create("new@example.com", "newbie", "$2b$12$exact-hash-string")
    fetched = await repo.get_by_id(user.id)
    assert fetched is not None
    assert fetched.hashed_password == "$2b$12$exact-hash-string"


async def test_duplicate_email_violates_unique_constraint(db_session):
    repo = SqlAlchemyUserRepository(db_session)
    await repo.create("dupe@example.com", "userone", "hash-one")
    with pytest.raises(IntegrityError):
        await repo.create("dupe@example.com", "usertwo", "hash-two")


async def test_duplicate_username_violates_unique_constraint(db_session):
    repo = SqlAlchemyUserRepository(db_session)
    await repo.create("a@example.com", "sameuser", "hash-one")
    with pytest.raises(IntegrityError):
        await repo.create("b@example.com", "sameuser", "hash-two")


# ---------------------------------------------------------------------------
# lookups
# ---------------------------------------------------------------------------


async def test_get_by_email_found(db_session):
    repo = SqlAlchemyUserRepository(db_session)
    created = await repo.create("find@example.com", "finder", "hash")
    found = await repo.get_by_email("find@example.com")
    assert found is not None
    assert found.id == created.id


async def test_get_by_email_not_found_returns_none(db_session):
    repo = SqlAlchemyUserRepository(db_session)
    assert await repo.get_by_email("ghost@example.com") is None


async def test_get_by_username_found(db_session):
    repo = SqlAlchemyUserRepository(db_session)
    created = await repo.create("find@example.com", "finder", "hash")
    found = await repo.get_by_username("finder")
    assert found is not None
    assert found.id == created.id


async def test_get_by_username_not_found_returns_none(db_session):
    repo = SqlAlchemyUserRepository(db_session)
    assert await repo.get_by_username("ghost") is None


async def test_get_by_id_found(db_session):
    repo = SqlAlchemyUserRepository(db_session)
    created = await repo.create("find@example.com", "finder", "hash")
    found = await repo.get_by_id(created.id)
    assert found is not None
    assert found.email == "find@example.com"


async def test_get_by_id_not_found_returns_none(db_session):
    repo = SqlAlchemyUserRepository(db_session)
    assert await repo.get_by_id(uuid4()) is None


# ---------------------------------------------------------------------------
# updates
# ---------------------------------------------------------------------------


async def test_update_username_persists(db_session):
    repo = SqlAlchemyUserRepository(db_session)
    user = await repo.create("u@example.com", "before", "hash")
    await repo.update_username(user.id, "after")
    assert (await repo.get_by_id(user.id)).username == "after"


async def test_update_password_bumps_version_and_hash(db_session):
    repo = SqlAlchemyUserRepository(db_session)
    user = await repo.create("u@example.com", "user", "old-hash")
    await repo.update_password(user.id, "new-hash", token_version=1)
    fetched = await repo.get_by_id(user.id)
    assert fetched.hashed_password == "new-hash"
    assert fetched.token_version == 1


async def test_set_email_verified_persists(db_session):
    repo = SqlAlchemyUserRepository(db_session)
    user = await repo.create("u@example.com", "user", "hash")
    assert user.email_verified is False
    await repo.set_email_verified(user.id)
    assert (await repo.get_by_id(user.id)).email_verified is True


async def test_returned_object_is_domain_entity_not_orm(db_session):
    """The repository maps ORM rows to the frozen domain dataclass."""
    from app.core.auth.model import User

    repo = SqlAlchemyUserRepository(db_session)
    user = await repo.create("domain@example.com", "domainer", "hash")
    assert type(user) is User
