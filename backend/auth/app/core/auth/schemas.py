import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# EmailStr already trims surrounding whitespace, caps total length, allows
# plus-tags and unicode local parts — no extra email validation needed here.

_PASSWORD_RULES: tuple[tuple[str, str], ...] = (
    (r"[A-Za-z]", "Password must contain at least one letter"),
    (r"\d", "Password must contain at least one digit"),
    (r"[^A-Za-z0-9]", "Password must contain at least one special character"),
)

_USERNAME_RE = re.compile(r"[a-z0-9_]+")


def _validate_password(value: str) -> str:
    for pattern, message in _PASSWORD_RULES:
        if re.search(pattern, value) is None:
            raise ValueError(message)
    return value


def _validate_username(value: str) -> str:
    value = value.strip().lower()
    if _USERNAME_RE.fullmatch(value) is None:
        raise ValueError(
            "Username may only contain lowercase letters, digits, and underscores"
        )
    return value


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)

    _v_username = field_validator("username")(_validate_username)
    _v_password = field_validator("password")(_validate_password)


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)

    _v_new = field_validator("new_password")(_validate_password)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)

    _v_new = field_validator("new_password")(_validate_password)


class ChangeUsernameRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)

    _v_username = field_validator("username")(_validate_username)


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    username: str
    email_verified: bool


class PublicUser(BaseModel):
    """Minimal user info exposed to other authenticated users (id → name)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
