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
    # Bumped on every password change/reset; tokens carry the version they were
    # minted at, so a change invalidates every previously issued token (global
    # logout) precisely — no wall-clock/iat-resolution races.
    token_version: int
