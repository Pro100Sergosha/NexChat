"""SmtpEmailSender against a stubbed aiosmtplib.send.

Pins the graceful no-op when credentials are absent (mirrors FCM without
creds), the message shape (From/To/Subject/body), and the From fallback to the
username when SMTP_FROM is unset."""

from datetime import UTC, datetime
from uuid import uuid4

import aiosmtplib
import pytest

from app.core.config import Settings
from app.core.notifications.model import Notification
from app.infra.email.client import SmtpEmailSender

NOTIFICATION = Notification(
    id=uuid4(),
    user_id="user-1",
    type="email_verification",
    title="Verify your email",
    body="Click: https://nexchat/verify?token=abc",
    data={},
    read=False,
    created_at=datetime.now(UTC),
)


def _settings(**overrides: object) -> Settings:
    base = {
        "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "REDIS_URL": "redis://localhost:6379/0",
        "RABBITMQ_URL": "amqp://guest:guest@localhost:5672/",
        "JWT_SECRET_KEY": "test-secret",
    }
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def captured_send(monkeypatch):
    calls: list[dict] = []

    async def fake_send(message, **kwargs):
        calls.append({"message": message, "kwargs": kwargs})

    monkeypatch.setattr(aiosmtplib, "send", fake_send)
    return calls


async def test_no_credentials_is_noop(captured_send):
    sender = SmtpEmailSender(_settings())  # no SMTP_USERNAME/PASSWORD

    await sender.send("user@example.com", NOTIFICATION)

    assert captured_send == []


async def test_missing_password_is_noop(captured_send):
    sender = SmtpEmailSender(_settings(SMTP_USERNAME="bot@nexchat.io"))

    await sender.send("user@example.com", NOTIFICATION)

    assert captured_send == []


async def test_send_builds_message_and_calls_smtp(captured_send):
    sender = SmtpEmailSender(
        _settings(
            SMTP_USERNAME="bot@nexchat.io",
            SMTP_PASSWORD="secret",
            SMTP_FROM="no-reply@nexchat.io",
        )
    )

    await sender.send("user@example.com", NOTIFICATION)

    assert len(captured_send) == 1
    message = captured_send[0]["message"]
    kwargs = captured_send[0]["kwargs"]
    assert message["From"] == "no-reply@nexchat.io"
    assert message["To"] == "user@example.com"
    assert message["Subject"] == "Verify your email"
    assert "verify?token=abc" in message.get_content()
    assert kwargs["hostname"] == "smtp.gmail.com"
    assert kwargs["port"] == 587
    assert kwargs["start_tls"] is True
    assert kwargs["username"] == "bot@nexchat.io"
    assert kwargs["password"] == "secret"


async def test_from_falls_back_to_username(captured_send):
    sender = SmtpEmailSender(
        _settings(SMTP_USERNAME="bot@nexchat.io", SMTP_PASSWORD="secret")
    )

    await sender.send("user@example.com", NOTIFICATION)

    assert captured_send[0]["message"]["From"] == "bot@nexchat.io"
