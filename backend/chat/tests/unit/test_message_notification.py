"""ChatService fans a new message out to the notifications service.

On every stored message the service publishes a notification aimed at the
*recipient* (the other 1:1 participant), never the sender. Online/offline
routing (SSE bell vs. FCM push) is the notifications service's job, driven by
its own presence — chat always publishes. Publishing is best-effort: a down
broker must not fail sending or storing the message (it is already persisted).
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

from app.core.chat.model import Conversation, Message
from app.core.chat.repository import NotificationPublisher
from app.core.chat.service import ChatService


class FakePublisher(NotificationPublisher):
    """Records publish calls (real port impl, not a mock); optionally blows up."""

    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[dict] = []
        self._fail = fail

    async def publish_message_notification(
        self,
        *,
        recipient_id: str,
        sender_id: str,
        conversation_id: int,
        message_id: int,
        content: str,
    ) -> None:
        if self._fail:
            raise RuntimeError("broker down")
        self.calls.append(
            {
                "recipient_id": recipient_id,
                "sender_id": sender_id,
                "conversation_id": conversation_id,
                "message_id": message_id,
                "content": content,
            }
        )


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


def _message(
    id: int = 10,
    conversation_id: int = 1,
    sender_id: str = "user-a",
    content: str = "hi",
) -> Message:
    return Message(
        id=id,
        conversation_id=conversation_id,
        sender_id=sender_id,
        content=content,
        created_at=datetime.now(UTC),
    )


def _service(conv_repo, msg_repo, publisher) -> ChatService:
    return ChatService(
        conversation_repo=conv_repo, message_repo=msg_repo, publisher=publisher
    )


class TestMessageNotification:
    async def test_notifies_recipient_not_sender(self):
        conv_repo = AsyncMock()
        conv_repo.get_by_pair.return_value = _conversation(
            user_a_id="user-a", user_b_id="user-b"
        )
        msg_repo = AsyncMock()
        msg_repo.create.return_value = _message(sender_id="user-a")
        publisher = FakePublisher()

        service = _service(conv_repo, msg_repo, publisher)
        await service.send_message(
            sender_id="user-a", recipient_id="user-b", content="hi"
        )

        assert len(publisher.calls) == 1
        assert publisher.calls[0]["recipient_id"] == "user-b"
        assert publisher.calls[0]["sender_id"] == "user-a"

    async def test_recipient_is_the_other_participant_when_sender_is_user_b(self):
        conv_repo = AsyncMock()
        conv_repo.get_by_pair.return_value = _conversation(
            user_a_id="user-a", user_b_id="user-b"
        )
        msg_repo = AsyncMock()
        msg_repo.create.return_value = _message(sender_id="user-b")
        publisher = FakePublisher()

        service = _service(conv_repo, msg_repo, publisher)
        await service.send_message(
            sender_id="user-b", recipient_id="user-a", content="hi"
        )

        assert publisher.calls[0]["recipient_id"] == "user-a"

    async def test_notification_carries_message_metadata(self):
        conv_repo = AsyncMock()
        conv_repo.get_by_id.return_value = _conversation(id=42)
        msg_repo = AsyncMock()
        # Repo stores the trimmed content, so the stored message carries "hello".
        msg_repo.create.return_value = _message(
            id=77, conversation_id=42, sender_id="user-a", content="hello"
        )
        publisher = FakePublisher()

        service = _service(conv_repo, msg_repo, publisher)
        await service.send_message(
            sender_id="user-a", conversation_id=42, content="  hello  "
        )

        call = publisher.calls[0]
        assert call["conversation_id"] == 42
        assert call["message_id"] == 77
        assert call["content"] == "hello"  # notifies with the stored (trimmed) body
        assert call["recipient_id"] == "user-b"

    async def test_best_effort_publish_failure_still_returns_message(self):
        conv_repo = AsyncMock()
        conv_repo.get_by_pair.return_value = _conversation()
        stored = _message()
        msg_repo = AsyncMock()
        msg_repo.create.return_value = stored
        publisher = FakePublisher(fail=True)

        service = _service(conv_repo, msg_repo, publisher)
        # A down broker must not propagate — the message is already persisted.
        result = await service.send_message(
            sender_id="user-a", recipient_id="user-b", content="hi"
        )

        assert result is stored

    async def test_no_notification_when_validation_fails(self):
        conv_repo = AsyncMock()
        msg_repo = AsyncMock()
        publisher = FakePublisher()

        service = _service(conv_repo, msg_repo, publisher)
        from app.core.chat.exceptions import MessageContentEmpty

        import pytest

        with pytest.raises(MessageContentEmpty):
            await service.send_message(
                sender_id="user-a", recipient_id="user-b", content="   "
            )

        assert publisher.calls == []
        msg_repo.create.assert_not_called()
