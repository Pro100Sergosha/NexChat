from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Notification:
    id: UUID
    user_id: str
    type: str
    title: str
    body: str
    data: dict[str, Any]
    read: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DeviceToken:
    id: UUID
    user_id: str
    token: str
    platform: str
    created_at: datetime
