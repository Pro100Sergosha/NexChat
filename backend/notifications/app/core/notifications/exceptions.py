from app.core.exception import AppException


class NotificationNotFound(AppException):
    """Raised when a notification id does not exist."""

    code = "notification_not_found"
    message = "Notification not found"


class DeviceTokenNotFound(AppException):
    """Raised when unregistering a device token that isn't stored."""

    code = "device_token_not_found"
    message = "Device token not found"


class NotAuthorized(AppException):
    """Raised when a caller acts on a resource owned by another user (IDOR)."""

    code = "not_authorized"
    message = "You are not allowed to access this resource"


class TokenExpired(AppException):
    """Raised when a JWT has expired."""

    code = "token_expired"
    message = "The token has expired"


class TokenInvalid(AppException):
    """Raised when a JWT is malformed, mis-signed, or of the wrong type."""

    code = "token_invalid"
    message = "The token is invalid"


class NotAuthenticated(AppException):
    """Raised when no valid Bearer credentials were presented at all."""

    code = "not_authenticated"
    message = "Authentication credentials were not provided"
