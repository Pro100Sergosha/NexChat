"""NotificationService.emit routing + device/history rules, with fake ports.

Pins the core delivery decision: online users get a live event-bus publish,
offline users fall back to FCM (pruning tokens FCM rejects), and ownership is
enforced on read-state and device unregister (IDOR)."""

from uuid import uuid4

import pytest

from app.core.notifications.exceptions import (
    DeviceTokenNotFound,
    NotAuthorized,
    NotificationNotFound,
)
from app.core.notifications.schemas import NotificationEvent
from app.infra.database.repositories import SqlAlchemyDeviceTokenRepository
from tests.conftest import make_device, make_notification

EVENT = NotificationEvent(
    user_id="user-1", type="message", title="Hi", body="hello", data={"k": "v"}
)


async def test_emit_online_publishes_to_bus(service, fakes):
    fakes.presence.set_online("user-1")

    notification = await service.emit(EVENT)

    assert notification.user_id == "user-1"
    assert len(fakes.event_bus.published) == 1
    published_user, payload = fakes.event_bus.published[0]
    assert published_user == "user-1"
    assert str(notification.id) in payload
    assert fakes.push.sent == []


async def test_emit_offline_sends_push(service, fakes, db_session):
    await make_device(db_session, user_id="user-1", token="tok-1")

    await service.emit(EVENT)

    assert len(fakes.push.sent) == 1
    assert fakes.event_bus.published == []


async def test_emit_offline_without_devices_skips_push(service, fakes):
    await service.emit(EVENT)

    assert fakes.push.sent == []
    assert fakes.event_bus.published == []


async def test_emit_offline_prunes_invalid_tokens(service, fakes, db_session):
    await make_device(db_session, user_id="user-1", token="good")
    await make_device(db_session, user_id="user-1", token="stale")
    fakes.push.invalid_tokens = {"stale"}

    await service.emit(EVENT)

    remaining = {
        t.token
        for t in await SqlAlchemyDeviceTokenRepository(db_session).list_for_user(
            "user-1"
        )
    }
    assert remaining == {"good"}


async def test_mark_read_sets_flag(service, db_session):
    notification = await make_notification(db_session, user_id="user-1")

    await service.mark_read("user-1", notification.id)

    refreshed = await service._notifications.get_by_id(notification.id)
    assert refreshed.read is True


async def test_mark_read_missing_raises(service):
    with pytest.raises(NotificationNotFound):
        await service.mark_read("user-1", uuid4())


async def test_mark_read_other_owner_raises(service, db_session):
    notification = await make_notification(db_session, user_id="user-1")

    with pytest.raises(NotAuthorized):
        await service.mark_read("user-2", notification.id)


async def test_register_device_is_idempotent(service):
    first = await service.register_device(
        user_id="user-1", token="tok", platform="web"
    )
    second = await service.register_device(
        user_id="user-1", token="tok", platform="web"
    )
    assert first.id == second.id


async def test_unregister_missing_raises(service):
    with pytest.raises(DeviceTokenNotFound):
        await service.unregister_device(user_id="user-1", token="nope")


async def test_unregister_other_owner_raises(service, db_session):
    await make_device(db_session, user_id="user-2", token="owned-by-b")

    with pytest.raises(NotAuthorized):
        await service.unregister_device(user_id="user-1", token="owned-by-b")
