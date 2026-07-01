from app.core.exception import AppException


class UserAlreadyExists(AppException):
    """Raised when registering an email that already exists."""


class UserNotFound(AppException):
    """Raised when a user cannot be found."""


class InvalidCredentials(AppException):
    """Raised when the email/password pair does not match."""


class TokenExpired(AppException):
    """Raised when a JWT has expired."""


class TokenInvalid(AppException):
    """Raised when a JWT is malformed, mis-signed, or of the wrong type."""


class TokenRevoked(AppException):
    """Raised when a JWT is present in the blacklist."""
