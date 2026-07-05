from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Platform = Literal["web", "android", "ios"]


class NotificationEvent(BaseModel):
    """Wire object carried by the broker from producer to the emit consumer.

    Deliberately transport-shaped (no id/created_at) — persistence happens
    inside the consumer, not at the producer.
    """

    user_id: str
    type: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=2000)
    data: dict[str, Any] = Field(default_factory=dict)
    # Forced-email recipient. When set, the emit pipeline also delivers over the
    # email channel to this address (transactional email, e.g. registration
    # verification). Plain str, not EmailStr — the trusted producer validates it.
    email: str | None = Field(default=None, max_length=320)


class NotificationEmitRequest(BaseModel):
    user_id: str = Field(min_length=1)
    type: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=2000)
    data: dict[str, Any] = Field(default_factory=dict)
    email: str | None = Field(default=None, max_length=320)


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: str
    type: str
    title: str
    body: str
    data: dict[str, Any]
    read: bool
    created_at: datetime


class DeviceTokenRegisterRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)
    platform: Platform


class DeviceTokenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    token: str
    platform: str
