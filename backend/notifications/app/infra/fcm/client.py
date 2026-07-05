import logging
import os

import firebase_admin
from anyio import to_thread
from firebase_admin import credentials, messaging

from app.core.config import Settings
from app.core.notifications.model import DeviceToken, Notification
from app.core.notifications.repository import PushSender

logger = logging.getLogger(__name__)

_APP_NAME = "notifications"


class FirebasePushSender(PushSender):
    """firebase-admin wrapper. Builds a per-platform FCM message and reports
    the tokens FCM rejects as unregistered so the caller can prune them.

    Credentials come from a service-account JSON *file* (path in
    FCM_CREDENTIALS_FILE, gitignored). If the path is unset or the file is
    missing the sender is a no-op (empty invalid set), so the offline path
    degrades gracefully instead of crashing the consumer.
    """

    def __init__(self, settings: Settings) -> None:
        self._app: firebase_admin.App | None = None
        creds_path = settings.FCM_CREDENTIALS_FILE
        if not creds_path:
            logger.warning("FCM disabled: FCM_CREDENTIALS_FILE is empty")
            return
        if not os.path.isfile(creds_path):
            logger.warning(
                "FCM disabled: credentials file not found at %r (cwd=%r)",
                creds_path,
                os.getcwd(),
            )
            return
        cred = credentials.Certificate(creds_path)
        try:
            self._app = firebase_admin.get_app(_APP_NAME)
        except ValueError:
            self._app = firebase_admin.initialize_app(cred, name=_APP_NAME)

    async def send(
        self, tokens: list[DeviceToken], notification: Notification
    ) -> set[str]:
        if self._app is None:
            logger.warning("FCM send skipped: sender not initialized (no credentials)")
            return set()
        if not tokens:
            logger.info("FCM send skipped: user has no registered device tokens")
            return set()
        # firebase-admin is blocking — keep the event loop free.
        return await to_thread.run_sync(self._send_sync, tokens, notification)

    def _send_sync(
        self, tokens: list[DeviceToken], notification: Notification
    ) -> set[str]:
        messages = [self._build(token, notification) for token in tokens]
        batch = messaging.send_each(messages, app=self._app)
        invalid: set[str] = set()
        for token, resp in zip(tokens, batch.responses, strict=True):
            if not resp.success and isinstance(
                resp.exception, messaging.UnregisteredError
            ):
                invalid.add(token.token)
        return invalid

    @staticmethod
    def _build(device: DeviceToken, notification: Notification) -> "messaging.Message":
        notif = messaging.Notification(title=notification.title, body=notification.body)
        data = {key: str(value) for key, value in notification.data.items()}
        kwargs: dict = {
            "token": device.token,
            "notification": notif,
            "data": data,
        }
        if device.platform == "web":
            kwargs["webpush"] = messaging.WebpushConfig(
                notification=messaging.WebpushNotification(
                    title=notification.title, body=notification.body
                )
            )
        elif device.platform == "android":
            kwargs["android"] = messaging.AndroidConfig(priority="high")
        elif device.platform == "ios":
            kwargs["apns"] = messaging.APNSConfig(
                payload=messaging.APNSPayload(aps=messaging.Aps(sound="default"))
            )
        return messaging.Message(**kwargs)
