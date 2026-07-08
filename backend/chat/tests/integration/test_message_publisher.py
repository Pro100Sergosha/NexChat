"""RabbitMQPublisher contract — the message chat puts on the wire must match the
``NotificationEvent`` shape the notifications service consumes.

chat is a producer only and never imports the notifications package, so this
test pins a local mirror of that wire contract and validates the published JSON
against it, plus the exchange/routing key. No real RabbitMQ —
``aio_pika.connect_robust`` is monkeypatched to capture the outgoing message.
"""

from unittest.mock import AsyncMock

import aio_pika
from pydantic import BaseModel, Field

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
        captured["message"] = message

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


async def test_publish_emits_valid_chat_message_event(monkeypatch):
    captured = _patched_broker(monkeypatch)

    publisher = RabbitMQPublisher("amqp://guest:guest@localhost/")
    await publisher.connect()
    await publisher.publish_message_notification(
        recipient_id="user-b",
        sender_id="user-a",
        conversation_id=42,
        message_id=77,
        content="hello there",
    )

    assert captured["routing_key"] == ROUTING_KEY
    event = _NotificationEvent.model_validate_json(captured["body"])
    assert event.user_id == "user-b"  # aimed at the recipient, not the sender
    assert event.type == "chat.message"
    assert event.email is None  # not the forced-email channel
    # FCM data values are all strings.
    assert event.data == {
        "conversation_id": "42",
        "message_id": "77",
        "sender_id": "user-a",
    }
    assert "hello there" in event.body


async def test_publish_declares_shared_topic_exchange_durable(monkeypatch):
    captured = _patched_broker(monkeypatch)

    publisher = RabbitMQPublisher("amqp://guest:guest@localhost/")
    await publisher.connect()

    captured["channel"].declare_exchange.assert_awaited_once()
    args, kwargs = captured["channel"].declare_exchange.await_args
    assert args[0] == EXCHANGE
    assert args[1] == aio_pika.ExchangeType.TOPIC
    assert kwargs["durable"] is True


async def test_body_is_truncated(monkeypatch):
    captured = _patched_broker(monkeypatch)

    publisher = RabbitMQPublisher("amqp://guest:guest@localhost/")
    await publisher.connect()
    await publisher.publish_message_notification(
        recipient_id="user-b",
        sender_id="user-a",
        conversation_id=1,
        message_id=1,
        content="x" * 5000,
    )

    event = _NotificationEvent.model_validate_json(captured["body"])
    assert len(event.body) <= 200


async def test_publish_is_noop_when_not_connected(monkeypatch):
    captured = _patched_broker(monkeypatch)

    publisher = RabbitMQPublisher("amqp://guest:guest@localhost/")
    # No connect() — nothing to publish through; must not raise.
    await publisher.publish_message_notification(
        recipient_id="user-b",
        sender_id="user-a",
        conversation_id=1,
        message_id=1,
        content="hi",
    )

    assert "body" not in captured
