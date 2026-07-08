import logging

from app.core.chat.exceptions import (
    ConversationNotFound,
    MessageContentEmpty,
    MessageTooLong,
    NotParticipant,
    SelfConversationNotAllowed,
)
from app.core.chat.model import Conversation, Message
from app.core.chat.repository import (
    ConversationRepository,
    MessageRepository,
    NotificationPublisher,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class ChatService:
    """Chat business logic: 1:1 conversations, message send/history.

    Depends only on repository/publisher ports. Ownership is enforced on every
    read/write (``has_participant``), and recipient notification is best-effort
    so a down broker never fails a send.
    """

    def __init__(
        self,
        conversation_repo: ConversationRepository,
        message_repo: MessageRepository,
        publisher: NotificationPublisher,
    ) -> None:
        self._conversation_repo = conversation_repo
        self._message_repo = message_repo
        self._publisher = publisher

    async def get_or_create_conversation(
        self, user_a_id: str, user_b_id: str
    ) -> Conversation:
        if user_a_id == user_b_id:
            raise SelfConversationNotAllowed()
        existing = await self._conversation_repo.get_by_pair(user_a_id, user_b_id)
        if existing is not None:
            return existing
        return await self._conversation_repo.create(user_a_id, user_b_id)

    async def send_message(
        self,
        *,
        sender_id: str,
        content: str,
        recipient_id: str | None = None,
        conversation_id: int | None = None,
    ) -> Message:
        """Persist a message and best-effort notify the other participant.

        Either ``conversation_id`` (sender must already be a participant, else
        ``NotParticipant`` / ``ConversationNotFound``) or ``recipient_id`` (the
        1:1 conversation is resolved or created) must be given. Content is
        stripped and length-checked. Notification failure never fails the send —
        the message is already persisted.
        """
        content = content.strip()
        if not content:
            raise MessageContentEmpty()
        if len(content) > settings.MESSAGE_MAX_LENGTH:
            raise MessageTooLong()

        if conversation_id is not None:
            conversation = await self._conversation_repo.get_by_id(conversation_id)
            if conversation is None:
                raise ConversationNotFound()
            if not conversation.has_participant(sender_id):
                raise NotParticipant()
        else:
            if sender_id == recipient_id:
                raise SelfConversationNotAllowed()
            conversation = await self.get_or_create_conversation(
                sender_id, recipient_id
            )

        message = await self._message_repo.create(
            conversation_id=conversation.id, sender_id=sender_id, content=content
        )
        await self._notify_recipient(conversation, message)
        logger.info(
            "message sent conversation=%s message=%s sender=%s",
            conversation.id,
            message.id,
            sender_id,
        )
        return message

    async def _notify_recipient(
        self, conversation: Conversation, message: Message
    ) -> None:
        # Always publish to the *other* participant; notifications decides
        # SSE-vs-FCM from its own presence, so we don't gate on chat sockets here.
        recipient_id = (
            conversation.user_b_id
            if conversation.user_a_id == message.sender_id
            else conversation.user_a_id
        )
        try:
            await self._publisher.publish_message_notification(
                recipient_id=recipient_id,
                sender_id=message.sender_id,
                conversation_id=conversation.id,
                message_id=message.id,
                content=message.content,
            )
        except Exception:
            # Best-effort: a down broker must not fail sending — the message is
            # already persisted (and broadcast over any live sockets by ws.py).
            logger.warning("message notification publish failed", exc_info=True)

    async def get_conversations_for_user(self, user_id: str) -> list[Conversation]:
        return await self._conversation_repo.list_for_user(user_id)

    async def get_messages(
        self, *, requester_id: str, conversation_id: int, limit: int, offset: int
    ) -> list[Message]:
        """Return a conversation's messages, newest-page first.

        A non-participant (or a missing conversation) gets the same
        ``ConversationNotFound`` — an outsider can't tell an unknown id from
        one they simply don't belong to (no existence leak). ``limit`` is capped
        at ``MAX_PAGE_SIZE``.
        """
        conversation = await self._conversation_repo.get_by_id(conversation_id)
        if conversation is None or not conversation.has_participant(requester_id):
            raise ConversationNotFound()
        limit = min(limit, settings.MAX_PAGE_SIZE)
        return await self._message_repo.list_for_conversation(
            conversation_id=conversation_id, limit=limit, offset=offset
        )
