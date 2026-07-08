"""WebSocket helpers for ``ws.py``: auth handshake, receive/persist, broadcast+ack.

Also owns ``_local_sockets`` — the single-process map of connection id → live
socket. ConnectionManager (Redis-backed) only tracks *presence* across instances;
pushing a frame needs the socket object itself, which never leaves this process.
"""

import json
import logging

from fastapi import WebSocket
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.chat.exceptions import (
    ConversationNotFound,
    MessageContentEmpty,
    MessageTooLong,
    NotParticipant,
    SelfConversationNotAllowed,
    TokenExpired,
    TokenInvalid,
)
from app.core.chat.model import Message
from app.core.chat.schemas import MessageOut, WSSendMessage
from app.core.chat.security import TokenVerifier
from app.core.chat.service import ChatService
from app.infra.database.repositories import SqlAlchemyConversationRepository
from app.infra.redis.connection_manager import ConnectionManager

logger = logging.getLogger(__name__)

_local_sockets: dict[int, WebSocket] = {}


def register_socket(connection_id: int, websocket: WebSocket) -> None:
    _local_sockets[connection_id] = websocket


def remove_socket(connection_id: int) -> None:
    _local_sockets.pop(connection_id, None)


async def authenticate(websocket: WebSocket, verifier: TokenVerifier) -> str | None:
    """Return the token's user_id, or close 4401 and return None on a bad token."""
    token = websocket.query_params.get("token") or ""
    try:
        return verifier.verify_access_token(token)
    except (TokenInvalid, TokenExpired):
        logger.warning("ws handshake rejected reason=bad_token")
        await websocket.close(code=4401)
        return None


async def message_loop(
    websocket: WebSocket,
    db: AsyncSession,
    service: ChatService,
    conversation_repo: SqlAlchemyConversationRepository,
    connection_manager: ConnectionManager,
    user_id: str,
) -> None:
    """Receive → persist → dispatch until the socket closes or a frame is rejected."""
    while True:
        message = await receive_message(websocket, service, user_id)
        if message is None:
            return
        await dispatch_message(
            websocket, db, conversation_repo, connection_manager, user_id, message
        )


async def receive_message(
    websocket: WebSocket, service: ChatService, user_id: str
) -> Message | None:
    """Receive one frame and persist it; close the socket and return None on failure.

    A None result means the caller must stop the loop — the socket is already
    closed with the appropriate code (4422 bad payload, 4403 not a participant,
    4422 invalid message).
    """
    raw = await websocket.receive_text()
    try:
        payload = WSSendMessage.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError):
        logger.warning("ws closed reason=bad_payload user=%s", user_id)
        await websocket.close(code=4422)
        return None

    try:
        return await service.send_message(
            sender_id=user_id,
            content=payload.content,
            recipient_id=payload.recipient_id,
            conversation_id=payload.conversation_id,
        )
    except (ConversationNotFound, NotParticipant):
        logger.warning("ws closed reason=not_participant user=%s", user_id)
        await websocket.close(code=4403)
        return None
    except (MessageContentEmpty, MessageTooLong, SelfConversationNotAllowed):
        logger.warning("ws closed reason=invalid_message user=%s", user_id)
        await websocket.close(code=4422)
        return None


async def dispatch_message(
    websocket: WebSocket,
    db: AsyncSession,
    conversation_repo: SqlAlchemyConversationRepository,
    connection_manager: ConnectionManager,
    user_id: str,
    message: Message,
) -> None:
    """Broadcast the message to the recipient's live sockets, then ack the sender.

    All DB work finishes before the ack: ``receive_json()`` on the client
    returns the instant the ack is sent, and closing that connection right after
    fires a cancel on this task — any DB call still in flight (e.g. this
    ``get_by_id``) could be cut off mid-operation and corrupt the connection.
    """
    frame = MessageOut.model_validate(message).model_dump(mode="json")

    conversation = await conversation_repo.get_by_id(message.conversation_id)
    recipient_id = (
        conversation.user_b_id
        if conversation.user_a_id == user_id
        else conversation.user_a_id
    )
    for conn_id in await connection_manager.connections_for(recipient_id):
        recipient_socket = _local_sockets.get(conn_id)
        if recipient_socket is not None:
            await recipient_socket.send_json(frame)

    await db.close()
    await websocket.send_json(frame)
