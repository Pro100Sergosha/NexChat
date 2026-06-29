# Auth Service

Port: 8000
Framework: FastAPI + SQLAlchemy (async) + Alembic + Redis

## Responsibilities

- User registration and login
- JWT access + refresh token issuance
- Token refresh endpoint
- Token revocation (logout) → blacklist in Redis
- Password hashing (bcrypt)

## Key files

| File | Purpose |
|---|---|
| `core/auth/model.py` | User domain entity |
| `core/auth/schemas.py` | Request/response Pydantic schemas |
| `core/auth/service.py` | Auth business logic (register, login, refresh, logout) |
| `core/auth/repository.py` | UserRepository interface |
| `core/auth/exceptions.py` | Domain exceptions (UserNotFound, InvalidCredentials, etc.) |
| `infra/database/models.py` | SQLAlchemy User model |
| `infra/database/repositories.py` | UserRepository implementation |
| `infra/redis/` | Token blacklist (check + add) |
| `infra/web/router.py` | Routes: POST /register, POST /login, POST /refresh, POST /logout |
| `infra/web/handler.py` | Endpoint handlers |
| `infra/web/dependables.py` | FastAPI dependencies (get_current_user, etc.) |

## JWT contract

- access token: short-lived (15 min), used for auth in chat service
- refresh token: long-lived (7d), stored client-side, used only on /refresh
- revoked tokens stored in Redis with TTL = token expiry
