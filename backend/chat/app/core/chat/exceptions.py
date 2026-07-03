from app.core.config import settings


class ChatAppException(Exception):  # noqa: N818  (domain base; subclasses name the failure)
    """Base class for all domain exceptions in the chat service."""

    code: str = "internal_error"
    message: str = "An unexpected error occurred"


class ConversationNotFound(ChatAppException):
    """Raised when a conversation id does not exist."""

    code = "conversation_not_found"
    message = "Conversation not found"


class NotParticipant(ChatAppException):
    """Raised when a user acts on a conversation they're not part of.

    Shares ConversationNotFound's (code, message) on purpose — a non-participant
    must see "not found", never "forbidden" (IDOR: existence shouldn't leak).
    """

    code = "conversation_not_found"
    message = "Conversation not found"


class SelfConversationNotAllowed(ChatAppException):
    """Raised when a user tries to start a conversation with themselves."""

    code = "self_conversation_not_allowed"
    message = "You cannot start a conversation with yourself"


class MessageContentEmpty(ChatAppException):
    """Raised when message content is empty or whitespace-only."""

    code = "message_content_empty"
    message = "Message content cannot be empty"


class MessageTooLong(ChatAppException):
    """Raised when message content exceeds the configured maximum length."""

    code = "message_too_long"
    message = (
        f"Message content exceeds the maximum length of "
        f"{settings.MESSAGE_MAX_LENGTH} characters"
    )


class TokenInvalid(ChatAppException):
    """Raised when a JWT is malformed, mis-signed, or of the wrong type."""

    code = "token_invalid"
    message = "The token is invalid"


class TokenExpired(ChatAppException):
    """Raised when a JWT has expired."""

    code = "token_expired"
    message = "The token has expired"


class NotAuthenticated(ChatAppException):
    """Raised when no valid Bearer credentials were presented at all."""

    code = "not_authenticated"
    message = "Authentication credentials were not provided"
