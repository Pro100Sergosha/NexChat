"""SqlAlchemyDeviceTokenRepository against a real sqlite engine, incl. the
unique-token constraint and bulk prune."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.infra.database.repositories import SqlAlchemyDeviceTokenRepository


async def test_add_and_get_by_token(db_session):
    repo = SqlAlchemyDeviceTokenRepository(db_session)

    added = await repo.add(user_id="user-1", token="tok", platform="android")

    fetched = await repo.get_by_token("tok")
    assert fetched is not None
    assert fetched.id == added.id
    assert fetched.platform == "android"


async def test_get_by_token_missing_returns_none(db_session):
    repo = SqlAlchemyDeviceTokenRepository(db_session)
    assert await repo.get_by_token("nope") is None


async def test_list_for_user_scoped(db_session):
    repo = SqlAlchemyDeviceTokenRepository(db_session)
    await repo.add(user_id="user-1", token="a", platform="web")
    await repo.add(user_id="user-2", token="b", platform="web")

    listed = await repo.list_for_user("user-1")
    assert {t.token for t in listed} == {"a"}


async def test_token_is_unique(db_session):
    repo = SqlAlchemyDeviceTokenRepository(db_session)
    await repo.add(user_id="user-1", token="dup", platform="web")

    with pytest.raises(IntegrityError):
        await repo.add(user_id="user-2", token="dup", platform="web")


async def test_remove(db_session):
    repo = SqlAlchemyDeviceTokenRepository(db_session)
    await repo.add(user_id="user-1", token="tok", platform="web")

    await repo.remove("tok")

    assert await repo.get_by_token("tok") is None


async def test_delete_many(db_session):
    repo = SqlAlchemyDeviceTokenRepository(db_session)
    await repo.add(user_id="user-1", token="a", platform="web")
    await repo.add(user_id="user-1", token="b", platform="web")
    await repo.add(user_id="user-1", token="c", platform="web")

    await repo.delete_many({"a", "c"})

    assert {t.token for t in await repo.list_for_user("user-1")} == {"b"}
