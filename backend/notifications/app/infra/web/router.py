from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Security, status
from fastapi.responses import Response

from app.core.notifications.repository import EventBus, NotificationBroker, Presence
from app.core.notifications.schemas import (
    DeviceTokenRegisterRequest,
    DeviceTokenResponse,
    NotificationEmitRequest,
    NotificationResponse,
)
from app.core.notifications.security import TokenVerifier
from app.core.notifications.service import NotificationService
from app.infra.web import handler
from app.infra.web.dependables import (
    get_broker,
    get_current_user_id,
    get_event_bus,
    get_notification_service,
    get_presence,
    get_token_verifier,
    oauth2_scheme,
    require_service_token,
)
from app.infra.web.sse import events_endpoint

# Routes mounted at the root; Nginx proxies /api/notifications/* and strips it.
router = APIRouter(tags=["notifications"])

ServiceDep = Annotated[NotificationService, Depends(get_notification_service)]
BrokerDep = Annotated[NotificationBroker, Depends(get_broker)]
UserIdDep = Annotated[str, Depends(get_current_user_id)]
PresenceDep = Annotated[Presence, Depends(get_presence)]
EventBusDep = Annotated[EventBus, Depends(get_event_bus)]
VerifierDep = Annotated[TokenVerifier, Depends(get_token_verifier)]


@router.get("/events")
async def events(
    request: Request,
    presence: PresenceDep,
    event_bus: EventBusDep,
    verifier: VerifierDep,
) -> Response:
    return await events_endpoint(request, presence, event_bus, verifier)


@router.post(
    "/notifications",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_service_token)],
)
async def emit(request: NotificationEmitRequest, broker: BrokerDep) -> None:
    # Producer-facing: authorized by X-Service-Token, not a user JWT. The
    # recipient (request.user_id) is arbitrary by design, so only trusted
    # producers may call this.
    await handler.emit(request, broker)


@router.get("/notifications", dependencies=[Security(oauth2_scheme)])
async def list_notifications(
    user_id: UserIdDep, service: ServiceDep
) -> list[NotificationResponse]:
    return await handler.list_notifications(user_id, service)


@router.post(
    "/notifications/{notification_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Security(oauth2_scheme)],
)
async def mark_read(
    notification_id: UUID, user_id: UserIdDep, service: ServiceDep
) -> None:
    await handler.mark_read(user_id, notification_id, service)


@router.post(
    "/devices",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Security(oauth2_scheme)],
)
async def register_device(
    request: DeviceTokenRegisterRequest, user_id: UserIdDep, service: ServiceDep
) -> DeviceTokenResponse:
    return await handler.register_device(request, user_id, service)


@router.delete(
    "/devices/{token}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Security(oauth2_scheme)],
)
async def unregister_device(
    token: str, user_id: UserIdDep, service: ServiceDep
) -> None:
    await handler.unregister_device(token, user_id, service)
