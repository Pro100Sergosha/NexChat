"""RabbitMQPublisher contract — the message auth puts on the wire must match the
``NotificationEvent`` shape the notifications service consumes.

auth deliberately does NOT import the notifications package, so this test pins a
local mirror of that wire contract and validates the published JSON against it,
plus the exchange/routing key. No real RabbitMQ — ``aio_pika.connect_robust`` is
monkeypatched to capture the outgoing message.
"""

from unittest.mock import AsyncMock

import aio_pika
from pydantic import BaseModel, Field

from app.core.config import settings
from app.infra.broker.config import EXCHANGE, ROUTING_KEY
from app.infra.broker.publisher import RabbitMQPublisher


class _NotificationEvent(BaseModel):
    """Mirror of notifications' broker wire object (kept in sync by this test)."""

    user_id: str
    type: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=2000)
    data: dict = {}
    email: str | None = Field(default=None, max_length=320)


def _patched_broker(monkeypatch) -> dict:
    captured: dict = {}
    exchange = AsyncMock()

    async def publish(message, routing_key):
        captured["body"] = message.body
        captured["routing_key"] = routing_key

    exchange.publish = publish
    channel = AsyncMock()
    channel.declare_exchange.return_value = exchange
    connection = AsyncMock()
    connection.channel.return_value = channel

    async def connect_robust(url):
        captured["url"] = url
        return connection

    monkeypatch.setattr(aio_pika, "connect_robust", connect_robust)
    captured["channel"] = channel
    return captured


async def test_publish_emits_valid_event_with_forced_email(monkeypatch):
    captured = _patched_broker(monkeypatch)

    publisher = RabbitMQPublisher(settings)
    await publisher.publish_verification(
        user_id="user-1",
        email="alice@example.com",
        verify_url="https://app.test/verify-email?token=abc.def",
    )

    assert captured["routing_key"] == ROUTING_KEY
    event = _NotificationEvent.model_validate_json(captured["body"])
    assert event.user_id == "user-1"
    assert event.email == "alice@example.com"  # forced-email channel
    assert event.data["verify_url"] == "https://app.test/verify-email?token=abc.def"
    assert "token=abc.def" in event.body


async def test_publish_declares_the_shared_exchange(monkeypatch):
    captured = _patched_broker(monkeypatch)

    publisher = RabbitMQPublisher(settings)
    await publisher.publish_verification(
        user_id="user-1", email="a@b.com", verify_url="https://x/verify?token=t"
    )

    captured["channel"].declare_exchange.assert_awaited_once()
    assert captured["channel"].declare_exchange.await_args.args[0] == EXCHANGE
