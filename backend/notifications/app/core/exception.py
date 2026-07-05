class AppException(Exception):  # noqa: N818  (domain base; subclasses name the failure)
    """Base class for all domain exceptions in the notifications service."""

    code: str = "internal_error"
    message: str = "An unexpected error occurred"
