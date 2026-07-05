"""SqlAlchemyNotificationRepository against a real sqlite engine."""

from uuid import uuid4

from app.infra.database.repositories import SqlAlchemyNotificationRepository


async def test_create_and_get_by_id(db_session):
    repo = SqlAlchemyNotificationRepository(db_session)

    created = await repo.create(
        user_id="user-1",
        type="message",
        title="Hi",
        body="hello",
        data={"conversation_id": "42"},
    )

    fetched = await repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.user_id == "user-1"
    assert fetched.data == {"conversation_id": "42"}
    assert fetched.read is False


async def test_get_by_id_missing_returns_none(db_session):
    repo = SqlAlchemyNotificationRepository(db_session)
    assert await repo.get_by_id(uuid4()) is None


async def test_list_for_user_scoped_and_ordered(db_session):
    repo = SqlAlchemyNotificationRepository(db_session)
    await repo.create(user_id="user-1", type="m", title="a", body="1", data={})
    await repo.create(user_id="user-1", type="m", title="b", body="2", data={})
    await repo.create(user_id="user-2", type="m", title="c", body="3", data={})

    listed = await repo.list_for_user("user-1")

    assert len(listed) == 2
    assert {n.title for n in listed} == {"a", "b"}
    # newest first
    assert listed[0].created_at >= listed[1].created_at


async def test_mark_read_persists(db_session):
    repo = SqlAlchemyNotificationRepository(db_session)
    created = await repo.create(
        user_id="user-1", type="m", title="a", body="1", data={}
    )

    await repo.mark_read(created.id)

    assert (await repo.get_by_id(created.id)).read is True
