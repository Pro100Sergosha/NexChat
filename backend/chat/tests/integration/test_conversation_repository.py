"""SqlAlchemyConversationRepository against a real (sqlite) session.

Verifies the persistence contract: round-trips, pair lookups that are
order-independent for the caller, and the unique constraint on a
(user_a_id, user_b_id) pair.

# TODO: only 1:1 pairs. A group-conversation model will need a separate
# participants table and a different uniqueness story.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.chat.model import Conversation
from app.infra.database.repositories import SqlAlchemyConversationRepository


async def test_create_returns_populated_conversation(db_session):
    repo = SqlAlchemyConversationRepository(db_session)
    conversation = await repo.create("user-a", "user-b")
    assert conversation.id is not None
    assert conversation.created_at is not None
    assert conversation.user_a_id == "user-a"
    assert conversation.user_b_id == "user-b"


async def test_get_by_id_found(db_session):
    repo = SqlAlchemyConversationRepository(db_session)
    created = await repo.create("user-a", "user-b")
    found = await repo.get_by_id(created.id)
    assert found is not None
    assert found.id == created.id


async def test_get_by_id_not_found_returns_none(db_session):
    repo = SqlAlchemyConversationRepository(db_session)
    assert await repo.get_by_id(999999) is None


async def test_get_by_pair_finds_a_b_order(db_session):
    repo = SqlAlchemyConversationRepository(db_session)
    created = await repo.create("user-a", "user-b")
    found = await repo.get_by_pair("user-a", "user-b")
    assert found is not None
    assert found.id == created.id


async def test_get_by_pair_finds_reversed_order(db_session):
    """Caller passes (B, A) — must still find the (A, B) row."""
    repo = SqlAlchemyConversationRepository(db_session)
    created = await repo.create("user-a", "user-b")
    found = await repo.get_by_pair("user-b", "user-a")
    assert found is not None
    assert found.id == created.id


async def test_get_by_pair_not_found_returns_none(db_session):
    repo = SqlAlchemyConversationRepository(db_session)
    assert await repo.get_by_pair("user-a", "user-b") is None


async def test_list_for_user_returns_only_own_conversations(db_session):
    repo = SqlAlchemyConversationRepository(db_session)
    mine = await repo.create("user-a", "user-b")
    await repo.create("user-c", "user-d")

    result = await repo.list_for_user("user-a")

    assert [c.id for c in result] == [mine.id]


async def test_list_for_user_finds_conversations_as_either_side(db_session):
    repo = SqlAlchemyConversationRepository(db_session)
    as_a = await repo.create("user-x", "user-b")
    as_b = await repo.create("user-c", "user-x")

    result = await repo.list_for_user("user-x")

    assert {c.id for c in result} == {as_a.id, as_b.id}


async def test_duplicate_literal_pair_violates_unique_constraint(db_session):
    repo = SqlAlchemyConversationRepository(db_session)
    await repo.create("user-a", "user-b")
    with pytest.raises(IntegrityError):
        await repo.create("user-a", "user-b")


async def test_returned_object_is_domain_entity_not_orm(db_session):
    repo = SqlAlchemyConversationRepository(db_session)
    conversation = await repo.create("user-a", "user-b")
    assert type(conversation) is Conversation
