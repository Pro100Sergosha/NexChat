"""SqlAlchemyMessageRepository against a real (sqlite) session.

Verifies persistence, ordering, pagination, and that deleting a
conversation cascades to its messages (FK ondelete=CASCADE).
"""

from app.core.chat.model import Message
from app.infra.database.repositories import (
    SqlAlchemyConversationRepository,
    SqlAlchemyMessageRepository,
)


async def test_create_returns_populated_message(db_session):
    conv_repo = SqlAlchemyConversationRepository(db_session)
    conversation = await conv_repo.create("user-a", "user-b")
    msg_repo = SqlAlchemyMessageRepository(db_session)

    message = await msg_repo.create(
        conversation_id=conversation.id, sender_id="user-a", content="hi"
    )

    assert message.id is not None
    assert message.created_at is not None
    assert message.content == "hi"


async def test_list_for_conversation_ordered_ascending(db_session):
    conv_repo = SqlAlchemyConversationRepository(db_session)
    conversation = await conv_repo.create("user-a", "user-b")
    msg_repo = SqlAlchemyMessageRepository(db_session)
    first = await msg_repo.create(
        conversation_id=conversation.id, sender_id="user-a", content="first"
    )
    second = await msg_repo.create(
        conversation_id=conversation.id, sender_id="user-b", content="second"
    )

    result = await msg_repo.list_for_conversation(
        conversation_id=conversation.id, limit=50, offset=0
    )

    assert [m.id for m in result] == [first.id, second.id]


async def test_list_for_conversation_only_own_conversation(db_session):
    conv_repo = SqlAlchemyConversationRepository(db_session)
    conv_a = await conv_repo.create("user-a", "user-b")
    conv_b = await conv_repo.create("user-c", "user-d")
    msg_repo = SqlAlchemyMessageRepository(db_session)
    await msg_repo.create(conversation_id=conv_a.id, sender_id="user-a", content="a")
    await msg_repo.create(conversation_id=conv_b.id, sender_id="user-c", content="b")

    result = await msg_repo.list_for_conversation(
        conversation_id=conv_a.id, limit=50, offset=0
    )

    assert len(result) == 1
    assert result[0].content == "a"


async def test_list_for_conversation_respects_limit(db_session):
    conv_repo = SqlAlchemyConversationRepository(db_session)
    conversation = await conv_repo.create("user-a", "user-b")
    msg_repo = SqlAlchemyMessageRepository(db_session)
    for i in range(5):
        await msg_repo.create(
            conversation_id=conversation.id, sender_id="user-a", content=f"msg-{i}"
        )

    result = await msg_repo.list_for_conversation(
        conversation_id=conversation.id, limit=2, offset=0
    )

    assert len(result) == 2


async def test_list_for_conversation_respects_offset(db_session):
    conv_repo = SqlAlchemyConversationRepository(db_session)
    conversation = await conv_repo.create("user-a", "user-b")
    msg_repo = SqlAlchemyMessageRepository(db_session)
    messages = [
        await msg_repo.create(
            conversation_id=conversation.id, sender_id="user-a", content=f"msg-{i}"
        )
        for i in range(3)
    ]

    result = await msg_repo.list_for_conversation(
        conversation_id=conversation.id, limit=50, offset=2
    )

    assert [m.id for m in result] == [messages[2].id]


async def test_list_for_conversation_empty_returns_empty_list(db_session):
    conv_repo = SqlAlchemyConversationRepository(db_session)
    conversation = await conv_repo.create("user-a", "user-b")
    msg_repo = SqlAlchemyMessageRepository(db_session)

    result = await msg_repo.list_for_conversation(
        conversation_id=conversation.id, limit=50, offset=0
    )

    assert result == []


async def test_deleting_conversation_cascades_to_messages(db_session):
    conv_repo = SqlAlchemyConversationRepository(db_session)
    conversation = await conv_repo.create("user-a", "user-b")
    msg_repo = SqlAlchemyMessageRepository(db_session)
    await msg_repo.create(
        conversation_id=conversation.id, sender_id="user-a", content="hi"
    )

    await conv_repo.delete(conversation.id)

    result = await msg_repo.list_for_conversation(
        conversation_id=conversation.id, limit=50, offset=0
    )
    assert result == []


async def test_returned_object_is_domain_entity_not_orm(db_session):
    conv_repo = SqlAlchemyConversationRepository(db_session)
    conversation = await conv_repo.create("user-a", "user-b")
    msg_repo = SqlAlchemyMessageRepository(db_session)

    message = await msg_repo.create(
        conversation_id=conversation.id, sender_id="user-a", content="hi"
    )

    assert type(message) is Message
