from app.core.chat.exceptions import (
    ConversationNotFound,
    MessageContentEmpty,
    MessageTooLong,
    NotParticipant,
    SelfConversationNotAllowed,
)
from app.core.chat.model import Conversation, Message
from app.core.chat.repository import ConversationRepository, MessageRepository
from app.core.config import settings


class ChatService:
    def __init__(
        self,
        conversation_repo: ConversationRepository,
        message_repo: MessageRepository,
    ) -> None:
        self._conversation_repo = conversation_repo
        self._message_repo = message_repo

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

        return await self._message_repo.create(
            conversation_id=conversation.id, sender_id=sender_id, content=content
        )

    async def get_conversations_for_user(self, user_id: str) -> list[Conversation]:
        return await self._conversation_repo.list_for_user(user_id)

    async def get_messages(
        self, *, requester_id: str, conversation_id: int, limit: int, offset: int
    ) -> list[Message]:
        conversation = await self._conversation_repo.get_by_id(conversation_id)
        if conversation is None or not conversation.has_participant(requester_id):
            raise ConversationNotFound()
        limit = min(limit, settings.MAX_PAGE_SIZE)
        return await self._message_repo.list_for_conversation(
            conversation_id=conversation_id, limit=limit, offset=offset
        )
