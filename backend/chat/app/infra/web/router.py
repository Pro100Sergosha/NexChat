from typing import Annotated

from fastapi import APIRouter, Depends, Query, Security
from fastapi.security import OAuth2PasswordBearer

from app.core.chat.schemas import ConversationOut, MessageOut
from app.core.chat.service import ChatService
from app.core.config import settings
from app.infra.web import handler
from app.infra.web.dependables import get_chat_service, get_current_user_id

router = APIRouter(tags=["chat"])

UserIdDep = Annotated[str, Depends(get_current_user_id)]
ServiceDep = Annotated[ChatService, Depends(get_chat_service)]
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="http://localhost:8000/login", auto_error=True)

@router.get("/conversations", dependencies=[Security(oauth2_scheme)])
async def get_conversations(
    user_id: UserIdDep, service: ServiceDep
) -> list[ConversationOut]:
    return await handler.get_conversations(user_id, service)


@router.get("/messages/{conversation_id}", dependencies=[Security(oauth2_scheme)])
async def get_messages(
    conversation_id: int,
    user_id: UserIdDep,
    service: ServiceDep,
    limit: Annotated[int, Query(gt=0)] = settings.DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[MessageOut]:
    return await handler.get_messages(user_id, conversation_id, limit, offset, service)
