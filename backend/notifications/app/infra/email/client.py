from email.message import EmailMessage

import aiosmtplib

from app.core.config import Settings
from app.core.notifications.model import Notification
from app.core.notifications.repository import EmailSender


class SmtpEmailSender(EmailSender):
    """aiosmtplib wrapper for the email delivery channel.

    Missing credentials (empty SMTP_USERNAME/SMTP_PASSWORD) make ``send`` a
    no-op — the email path degrades gracefully instead of crashing the consumer,
    mirroring FirebasePushSender without credentials. The From header falls back
    to the username when SMTP_FROM is unset.
    """

    def __init__(self, settings: Settings) -> None:
        self._host = settings.SMTP_HOST
        self._port = settings.SMTP_PORT
        self._use_tls = settings.SMTP_USE_TLS
        self._username = settings.SMTP_USERNAME
        self._password = settings.SMTP_PASSWORD
        self._from = settings.SMTP_FROM or settings.SMTP_USERNAME

    async def send(self, address: str, notification: Notification) -> None:
        if not self._username or not self._password:
            return
        message = self._build(address, notification)
        await aiosmtplib.send(
            message,
            hostname=self._host,
            port=self._port,
            start_tls=self._use_tls,
            username=self._username,
            password=self._password,
        )

    def _build(self, address: str, notification: Notification) -> EmailMessage:
        message = EmailMessage()
        message["From"] = self._from
        message["To"] = address
        message["Subject"] = notification.title
        message.set_content(notification.body)
        return message
