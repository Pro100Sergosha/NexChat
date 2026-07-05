# Auth Service

Port: 8000
Framework: FastAPI + SQLAlchemy (async) + Alembic + Redis + RabbitMQ

## Responsibilities

- User registration and login
- Email verification on registration (owns the `email_verified` flag)
- Unique `username` per account (+ id↔username lookup for other services/clients)
- JWT access + refresh token issuance
- Token refresh endpoint
- Token revocation (logout) → blacklist in Redis
- Password hashing (bcrypt); authenticated change + emailed reset
- Global logout via a per-user `token_version` (bumped on password change/reset)

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
| `infra/broker/` | `RabbitMQPublisher` — publishes the verification + password-reset emails to notifications |
| `infra/web/router.py` | Routes: POST /register, /login, /verify-email, /resend-verification, /change-password, /forgot-password, /reset-password, /change-username, /refresh, /logout, GET /me, /users/{id}, /users/by-username/{username} |
| `infra/web/handler.py` | Endpoint handlers |
| `infra/web/dependables.py` | FastAPI dependencies (get_current_user, etc.) |

## JWT contract

- access token: short-lived (15 min), used for auth in chat service
- refresh token: long-lived (7d), stored client-side, used only on /refresh
- verify token: `type=verify`, TTL `verify_token_expire_hours` (default 24h),
  single-use — the `jti` is blacklisted on redemption so the link can't replay
- reset token: `type=reset`, TTL `reset_token_expire_hours` (default 1h),
  single-use (jti blacklisted on redemption)
- access + refresh carry a `ver` claim = the user's `token_version` at mint time;
  `get_current_user` / `/refresh` reject a token whose `ver` != the stored version
  (this is the global-logout mechanism — see Password management)
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

## Password management

- **Global logout** rides on `users.token_version` (int, default 0). Every access
  and refresh token embeds the `ver` it was minted at; a mismatch with the stored
  version is rejected as `token_revoked` (401) in `get_current_user` and `/refresh`.
  This is precise regardless of clock/iat resolution — no timestamp races.
- `POST /change-password {current_password, new_password, logout_other_sessions?}`
  (Bearer) → 200 + a **fresh `TokenPair`** minted at the resulting version, so the
  caller always stays logged in. Wrong current password → 401 `invalid_credentials`.
  - `logout_other_sessions` (default `true`) bumps `token_version` → every *other*
    outstanding session dies. Set `false` to leave other devices logged in
    (version unchanged, only the hash rotates).
- `POST /forgot-password {email}` → always 202 empty (anti-enumeration); only a
  real account is mailed a `type=reset` link, throttled per address.
- `POST /reset-password {token, new_password}` → 204; **always** bumps
  `token_version` (compromise assumption → force global logout) and blacklists the
  reset jti. Spent link → 409/`token_revoked`; bad/expired/wrong-type → 401.
- Reset email is published like verification (forced-email `NotificationEvent`,
  best-effort); needs `EMAIL_RESET_URL_BASE` (defaults to the gateway).

## Usernames & lookup

- `username` is required at registration, unique (case-insensitive, stored
  lowercase), 3–32 chars `[a-z0-9_]`. Clash → 409 `username_taken`. Exposed on
  `UserResponse` (`/register`, `/me`). Login is still by **email**, not username.
- `POST /change-username {username}` (Bearer) → 200 `UserResponse`; uniqueness
  re-checked (409 on clash).
- `GET /users/{id}` and `GET /users/by-username/{username}` (Bearer) → `PublicUser
  {id, username}` only (never email / hash); unknown → 404 `user_not_found`. These
  let other services / the frontend resolve ids to display names without crossing
  into auth's DB.

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
