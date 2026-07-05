# Auth Service

Port: 8000
Framework: FastAPI + SQLAlchemy (async) + Alembic + Redis + RabbitMQ

## Responsibilities

- User registration and login
- Email verification on registration (owns the `email_verified` flag)
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
| `infra/broker/` | `RabbitMQPublisher` — publishes the verification email to notifications |
| `infra/web/router.py` | Routes: POST /register, /login, /verify-email, /resend-verification, /refresh, /logout, GET /me |
| `infra/web/handler.py` | Endpoint handlers |
| `infra/web/dependables.py` | FastAPI dependencies (get_current_user, etc.) |

## JWT contract

- access token: short-lived (15 min), used for auth in chat service
- refresh token: long-lived (7d), stored client-side, used only on /refresh
- verify token: `type=verify`, TTL `verify_token_expire_hours` (default 24h),
  single-use — the `jti` is blacklisted on redemption so the link can't replay
- revoked tokens stored in Redis with TTL = token expiry

## Email verification

- `register` creates the user `email_verified=False`, mints a verify JWT, and
  publishes a `NotificationEvent` to RabbitMQ (exchange `nexchat.notifications`,
  routing `notification.emit`) with a forced `email` + `{EMAIL_VERIFY_URL_BASE}?token=…`
  link. notifications delivers it over SMTP (forced-email channel). Publishing is
  **best-effort**: a down broker still returns 201 — the user recovers via resend.
- auth is a broker *producer only*; it never imports the notifications package —
  `RabbitMQPublisher` builds the `NotificationEvent` wire shape by hand.
- `POST /verify-email {token}` → 204, sets `email_verified=True`, revokes the jti.
  A spent/already-verified link → 409 `email_already_verified`.
- `login` is **gated**: an unverified account raises `email_not_verified` (403).
  The check sits *after* the password verification so a wrong password still
  returns the identical `invalid_credentials` (no user enumeration via the gate).
- `POST /resend-verification {email}` → always 202 empty body (anti-enumeration);
  only a real unverified user is re-sent to, throttled per address.
- Requires `RABBITMQ_URL` (env); `EMAIL_VERIFY_URL_BASE` defaults to the gateway.

## Login contract

`/login` is OAuth2 password form (`username`/`password`, form-encoded), not
JSON — works with the Swagger "Authorize" button. `username` is the email.

## Error contract

Every error response is `{"code": "<snake_case>", "message": "<human-readable
English sentence>"}` — see `.claude/TESTING.md` for the full convention and
the pinned catalog in `tests/web/test_exception_mapping.py`.

## Tests

Full pyramid under `tests/` (unit/integration/web/api) — see `.claude/TESTING.md`
for the cross-service testing conventions this service follows.
