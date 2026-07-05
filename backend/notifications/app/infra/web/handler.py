from uuid import UUID

from app.core.notifications.repository import NotificationBroker
from app.core.notifications.schemas import (
    DeviceTokenRegisterRequest,
    DeviceTokenResponse,
    NotificationEmitRequest,
    NotificationEvent,
    NotificationResponse,
)
from app.core.notifications.service import NotificationService


async def emit(request: NotificationEmitRequest, broker: NotificationBroker) -> None:
    """Manual/secondary path: publish onto the same broker the consumer drains,
    so there is a single delivery path. Returns nothing (202 Accepted)."""
    await broker.publish(NotificationEvent(**request.model_dump()))


async def list_notifications(
    user_id: str, service: NotificationService
) -> list[NotificationResponse]:
    notifications = await service.list_for_user(user_id)
    return [NotificationResponse.model_validate(n) for n in notifications]


async def mark_read(
    user_id: str, notification_id: UUID, service: NotificationService
) -> None:
    await service.mark_read(user_id, notification_id)


async def register_device(
    request: DeviceTokenRegisterRequest, user_id: str, service: NotificationService
) -> DeviceTokenResponse:
    device = await service.register_device(
        user_id=user_id, token=request.token, platform=request.platform
    )
    return DeviceTokenResponse.model_validate(device)


async def unregister_device(
    token: str, user_id: str, service: NotificationService
) -> None:
    await service.unregister_device(user_id=user_id, token=token)
