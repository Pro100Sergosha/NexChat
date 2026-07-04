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


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def _password_complexity(cls, value: str) -> str:
        for pattern, message in _PASSWORD_RULES:
            if re.search(pattern, value) is None:
                raise ValueError(message)
        return value


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
