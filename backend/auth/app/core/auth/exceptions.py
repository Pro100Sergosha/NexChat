from app.core.exception import AppException


class UserAlreadyExists(AppException):
    """Raised when registering an email that already exists."""

    code = "user_already_exists"
    message = "A user with this email already exists"


class UserNotFound(AppException):
    """Raised when a user cannot be found."""

    code = "user_not_found"
    message = "User not found"


class InvalidCredentials(AppException):
    """Raised when the email/password pair does not match."""

    code = "invalid_credentials"
    message = "Email or password is incorrect"


class TokenExpired(AppException):
    """Raised when a JWT has expired."""

    code = "token_expired"
    message = "The token has expired"


class TokenInvalid(AppException):
    """Raised when a JWT is malformed, mis-signed, or of the wrong type."""

    code = "token_invalid"
    message = "The token is invalid"


class TokenRevoked(AppException):
    """Raised when a JWT is present in the blacklist."""

    code = "token_revoked"
    message = "The token has been revoked"


class NotAuthenticated(AppException):
    """Raised when no valid Bearer credentials were presented at all."""

    code = "not_authenticated"
    message = "Authentication credentials were not provided"
