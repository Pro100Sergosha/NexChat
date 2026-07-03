from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.core.chat.exceptions import (
    ConversationNotFound,
    MessageContentEmpty,
    MessageTooLong,
    NotParticipant,
    SelfConversationNotAllowed,
)
from app.core.chat.model import Conversation
from app.core.chat.service import ChatService
from app.core.config import settings


def _conversation(
    id: int = 1, user_a_id: str = "user-a", user_b_id: str = "user-b"
) -> Conversation:
    return Conversation(
        id=id,
        user_a_id=user_a_id,
        user_b_id=user_b_id,
        created_at=datetime.now(UTC),
        last_message_at=None,
    )


def _service(conversation_repo=None, message_repo=None) -> ChatService:
    return ChatService(
        conversation_repo=conversation_repo or AsyncMock(),
        message_repo=message_repo or AsyncMock(),
    )


# ---------------------------------------------------------------------------
# get_or_create_conversation
# ---------------------------------------------------------------------------


class TestGetOrCreateConversation:
    async def test_returns_existing_pair_in_a_b_order(self):
        repo = AsyncMock()
        existing = _conversation()
        repo.get_by_pair.return_value = existing

        service = _service(conversation_repo=repo)
        result = await service.get_or_create_conversation("user-a", "user-b")

        assert result is existing
        repo.create.assert_not_called()

    async def test_returns_existing_pair_in_b_a_order(self):
        repo = AsyncMock()
        existing = _conversation()
        repo.get_by_pair.return_value = existing

        service = _service(conversation_repo=repo)
        result = await service.get_or_create_conversation("user-b", "user-a")

        assert result is existing
        repo.create.assert_not_called()

    async def test_creates_new_pair_when_absent(self):
        repo = AsyncMock()
        repo.get_by_pair.return_value = None
        created = _conversation()
        repo.create.return_value = created

        service = _service(conversation_repo=repo)
        result = await service.get_or_create_conversation("user-a", "user-b")

        assert result is created
        repo.create.assert_awaited_once()

    async def test_self_chat_rejected(self):
        repo = AsyncMock()
        service = _service(conversation_repo=repo)

        with pytest.raises(SelfConversationNotAllowed):
            await service.get_or_create_conversation("user-a", "user-a")
        repo.get_by_pair.assert_not_called()
        repo.create.assert_not_called()


# ---------------------------------------------------------------------------
# send_message
# ---------------------------------------------------------------------------


class TestSendMessage:
    async def test_new_recipient_creates_conversation(self):
        conv_repo = AsyncMock()
        conv_repo.get_by_pair.return_value = None
        conv_repo.create.return_value = _conversation()
        msg_repo = AsyncMock()
        msg_repo.create.return_value = AsyncMock(content="hi")

        service = _service(conversation_repo=conv_repo, message_repo=msg_repo)
        await service.send_message(
            sender_id="user-a", recipient_id="user-b", content="hi"
        )

        conv_repo.create.assert_awaited_once()
        msg_repo.create.assert_awaited_once()

    async def test_existing_recipient_reuses_conversation(self):
        conv_repo = AsyncMock()
        existing = _conversation()
        conv_repo.get_by_pair.return_value = existing
        msg_repo = AsyncMock()

        service = _service(conversation_repo=conv_repo, message_repo=msg_repo)
        await service.send_message(
            sender_id="user-a", recipient_id="user-b", content="hi"
        )

        conv_repo.create.assert_not_called()
        _, kwargs = msg_repo.create.await_args
        assert kwargs["conversation_id"] == existing.id

    async def test_send_into_known_conversation_id(self):
        conv_repo = AsyncMock()
        existing = _conversation(id=42)
        conv_repo.get_by_id.return_value = existing
        msg_repo = AsyncMock()

        service = _service(conversation_repo=conv_repo, message_repo=msg_repo)
        await service.send_message(sender_id="user-a", conversation_id=42, content="hi")

        conv_repo.get_by_pair.assert_not_called()
        _, kwargs = msg_repo.create.await_args
        assert kwargs["conversation_id"] == 42

    async def test_sender_not_participant_of_conversation_id_rejected(self):
        conv_repo = AsyncMock()
        conv_repo.get_by_id.return_value = _conversation(
            user_a_id="user-a", user_b_id="user-b"
        )
        msg_repo = AsyncMock()

        service = _service(conversation_repo=conv_repo, message_repo=msg_repo)
        with pytest.raises(NotParticipant):
            await service.send_message(
                sender_id="user-c", conversation_id=1, content="hi"
            )
        msg_repo.create.assert_not_called()

    async def test_unknown_conversation_id_raises_not_found(self):
        conv_repo = AsyncMock()
        conv_repo.get_by_id.return_value = None
        msg_repo = AsyncMock()

        service = _service(conversation_repo=conv_repo, message_repo=msg_repo)
        with pytest.raises(ConversationNotFound):
            await service.send_message(
                sender_id="user-a", conversation_id=999, content="hi"
            )

    async def test_content_is_trimmed(self):
        conv_repo = AsyncMock()
        conv_repo.get_by_pair.return_value = _conversation()
        msg_repo = AsyncMock()

        service = _service(conversation_repo=conv_repo, message_repo=msg_repo)
        await service.send_message(
            sender_id="user-a", recipient_id="user-b", content="  hi  "
        )

        _, kwargs = msg_repo.create.await_args
        assert kwargs["content"] == "hi"

    async def test_empty_content_rejected(self):
        service = _service()
        with pytest.raises(MessageContentEmpty):
            await service.send_message(
                sender_id="user-a", recipient_id="user-b", content=""
            )

    async def test_whitespace_only_content_rejected(self):
        service = _service()
        with pytest.raises(MessageContentEmpty):
            await service.send_message(
                sender_id="user-a", recipient_id="user-b", content="   "
            )

    async def test_content_over_max_length_rejected(self):
        service = _service()
        with pytest.raises(MessageTooLong):
            await service.send_message(
                sender_id="user-a",
                recipient_id="user-b",
                content="x" * (settings.MESSAGE_MAX_LENGTH + 1),
            )

    async def test_content_at_exactly_max_length_accepted(self):
        conv_repo = AsyncMock()
        conv_repo.get_by_pair.return_value = _conversation()
        msg_repo = AsyncMock()

        service = _service(conversation_repo=conv_repo, message_repo=msg_repo)
        await service.send_message(
            sender_id="user-a",
            recipient_id="user-b",
            content="x" * settings.MESSAGE_MAX_LENGTH,
        )

        msg_repo.create.assert_awaited_once()

    async def test_self_message_rejected(self):
        service = _service()
        with pytest.raises(SelfConversationNotAllowed):
            await service.send_message(
                sender_id="user-a", recipient_id="user-a", content="hi"
            )


# ---------------------------------------------------------------------------
# get_conversations_for_user
# ---------------------------------------------------------------------------


class TestGetConversationsForUser:
    async def test_returns_repo_result_as_is(self):
        repo = AsyncMock()
        conversations = [_conversation(id=1), _conversation(id=2)]
        repo.list_for_user.return_value = conversations

        service = _service(conversation_repo=repo)
        result = await service.get_conversations_for_user("user-a")

        assert result == conversations
        repo.list_for_user.assert_awaited_once_with("user-a")

    async def test_empty_list_passthrough(self):
        repo = AsyncMock()
        repo.list_for_user.return_value = []

        service = _service(conversation_repo=repo)
        result = await service.get_conversations_for_user("user-a")

        assert result == []


# ---------------------------------------------------------------------------
# get_messages
# ---------------------------------------------------------------------------


class TestGetMessages:
    async def test_returns_messages_for_participant(self):
        conv_repo = AsyncMock()
        conv_repo.get_by_id.return_value = _conversation()
        msg_repo = AsyncMock()
        msg_repo.list_for_conversation.return_value = []

        service = _service(conversation_repo=conv_repo, message_repo=msg_repo)
        await service.get_messages(
            requester_id="user-a", conversation_id=1, limit=50, offset=0
        )

        msg_repo.list_for_conversation.assert_awaited_once_with(
            conversation_id=1, limit=50, offset=0
        )

    async def test_unknown_conversation_raises_not_found(self):
        conv_repo = AsyncMock()
        conv_repo.get_by_id.return_value = None

        service = _service(conversation_repo=conv_repo)
        with pytest.raises(ConversationNotFound):
            await service.get_messages(
                requester_id="user-a", conversation_id=999, limit=50, offset=0
            )

    async def test_non_participant_raises_not_found(self):
        """IDOR: a non-participant sees "not found", not "forbidden"."""
        conv_repo = AsyncMock()
        conv_repo.get_by_id.return_value = _conversation(
            user_a_id="user-a", user_b_id="user-b"
        )

        service = _service(conversation_repo=conv_repo)
        with pytest.raises(ConversationNotFound):
            await service.get_messages(
                requester_id="user-c", conversation_id=1, limit=50, offset=0
            )

    async def test_limit_above_max_is_clamped(self):
        conv_repo = AsyncMock()
        conv_repo.get_by_id.return_value = _conversation()
        msg_repo = AsyncMock()
        msg_repo.list_for_conversation.return_value = []

        service = _service(conversation_repo=conv_repo, message_repo=msg_repo)
        await service.get_messages(
            requester_id="user-a", conversation_id=1, limit=100_000, offset=0
        )

        msg_repo.list_for_conversation.assert_awaited_once_with(
            conversation_id=1, limit=settings.MAX_PAGE_SIZE, offset=0
        )
