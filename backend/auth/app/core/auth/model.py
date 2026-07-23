from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    email: str
    username: str
    hashed_password: str
    created_at: datetime
    email_verified: bool
    token_version: int
