import json
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
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
from app.core.chat.schemas import MessageOut, WSSendMessage
from app.core.chat.security import TokenVerifier
from app.core.chat.service import ChatService
from app.infra.database.repositories import (
    SqlAlchemyConversationRepository,
    SqlAlchemyMessageRepository,
)
from app.infra.redis.connection_manager import ConnectionManager
from app.infra.web.dependables import get_connection_manager, get_db, get_token_verifier

router = APIRouter()

# Local, single-process map of connection id -> live socket. ConnectionManager
# (Redis-backed) only tracks *presence* across instances; actually pushing a
# frame requires the socket object itself, which never leaves this process.
_local_sockets: dict[int, WebSocket] = {}


@router.websocket("/ws")
async def ws_endpoint(
    websocket: WebSocket,
    db: Annotated[AsyncSession, Depends(get_db)],
    connection_manager: Annotated[ConnectionManager, Depends(get_connection_manager)],
    verifier: Annotated[TokenVerifier, Depends(get_token_verifier)],
) -> None:
    token = websocket.query_params.get("token") or ""
    try:
        user_id = verifier.verify_access_token(token)
    except (TokenInvalid, TokenExpired):
        await websocket.close(code=4401)
        return

    await websocket.accept()
    connection_id = id(websocket)
    _local_sockets[connection_id] = websocket
    await connection_manager.register(user_id, connection_id)

    conversation_repo = SqlAlchemyConversationRepository(db)
    service = ChatService(
        conversation_repo=conversation_repo,
        message_repo=SqlAlchemyMessageRepository(db),
    )

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = WSSendMessage.model_validate(json.loads(raw))
            except (json.JSONDecodeError, ValidationError):
                await websocket.close(code=4422)
                return

            try:
                message = await service.send_message(
                    sender_id=user_id,
                    content=payload.content,
                    recipient_id=payload.recipient_id,
                    conversation_id=payload.conversation_id,
                )
            except (ConversationNotFound, NotParticipant):
                await websocket.close(code=4403)
                return
            except (MessageContentEmpty, MessageTooLong, SelfConversationNotAllowed):
                await websocket.close(code=4422)
                return

            frame = MessageOut.model_validate(message).model_dump(mode="json")

            # All DB work for this message must finish *before* we ack the
            # sender: receive_json() on the client returns the instant the
            # ack is sent, and closing that connection right after fires a
            # cancel on our task with no synchronization — any DB call still
            # in flight at that point (e.g. this get_by_id) can be cut off
            # mid-operation and corrupt the shared test connection.
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
    except WebSocketDisconnect:
        pass
    finally:
        await connection_manager.unregister(user_id, connection_id)
        _local_sockets.pop(connection_id, None)
