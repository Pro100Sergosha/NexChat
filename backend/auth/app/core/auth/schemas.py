from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    # TODO: pin email edge cases — over-length, unicode local part,
    # surrounding whitespace, plus-tags.
    email: EmailStr
    # TODO: enforce password complexity (>=1 digit, >=1 letter) and pin
    # unicode/whitespace-only/null-byte handling.
    password: str = Field(min_length=8, max_length=128)


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
