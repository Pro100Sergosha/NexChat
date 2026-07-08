import logging
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.chat.repository import NotificationPublisher
from app.core.chat.security import TokenVerifier
from app.core.chat.service import ChatService
from app.infra.database.repositories import (
    SqlAlchemyConversationRepository,
    SqlAlchemyMessageRepository,
)
from app.infra.redis.connection_manager import ConnectionManager
from app.infra.web import ws_utils
from app.infra.web.dependables import (
    get_connection_manager,
    get_db,
    get_notification_publisher,
    get_token_verifier,
)

router = APIRouter()

logger = logging.getLogger(__name__)


@router.websocket("/ws")
async def ws_endpoint(
    websocket: WebSocket,
    db: Annotated[AsyncSession, Depends(get_db)],
    connection_manager: Annotated[ConnectionManager, Depends(get_connection_manager)],
    verifier: Annotated[TokenVerifier, Depends(get_token_verifier)],
    publisher: Annotated[NotificationPublisher, Depends(get_notification_publisher)],
) -> None:
    """WebSocket entrypoint: authenticate → accept → run the message loop.

    Close-code contract (no HTTP status on a WS): 4401 bad token (before
    ``.accept()``), 4403 not a participant, 4422 malformed/oversized payload.
    """
    user_id = await ws_utils.authenticate(websocket, verifier)
    if user_id is None:
        return

    await websocket.accept()
    connection_id = id(websocket)
    ws_utils.register_socket(connection_id, websocket)
    await connection_manager.register(user_id, connection_id)
    logger.info("ws connected user=%s", user_id)

    conversation_repo = SqlAlchemyConversationRepository(db)
    service = ChatService(
        conversation_repo=conversation_repo,
        message_repo=SqlAlchemyMessageRepository(db),
        publisher=publisher,
    )

    try:
        await ws_utils.message_loop(
            websocket, db, service, conversation_repo, connection_manager, user_id
        )
    except WebSocketDisconnect:
        pass
    finally:
        await connection_manager.unregister(user_id, connection_id)
        ws_utils.remove_socket(connection_id)
        logger.info("ws disconnected user=%s", user_id)
