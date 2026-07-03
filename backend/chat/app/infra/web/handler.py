from app.core.chat.schemas import ConversationOut, MessageOut
from app.core.chat.service import ChatService


async def get_conversations(
    user_id: str, service: ChatService
) -> list[ConversationOut]:
    conversations = await service.get_conversations_for_user(user_id)
    return [
        ConversationOut(
            id=c.id,
            other_user_id=c.user_b_id if c.user_a_id == user_id else c.user_a_id,
            created_at=c.created_at,
            last_message_at=c.last_message_at,
        )
        for c in conversations
    ]


async def get_messages(
    user_id: str,
    conversation_id: int,
    limit: int,
    offset: int,
    service: ChatService,
) -> list[MessageOut]:
    messages = await service.get_messages(
        requester_id=user_id,
        conversation_id=conversation_id,
        limit=limit,
        offset=offset,
    )
    return [MessageOut.model_validate(m) for m in messages]
