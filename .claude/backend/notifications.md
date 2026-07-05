# Notifications Service

Port: 8002
Framework: FastAPI + SQLAlchemy (async) + Alembic + Redis + RabbitMQ + SSE + FCM

Generic layer/style conventions live in `.claude/backend/style.md` — this doc is
only the notifications-specific design. It mirrors `auth`'s scaffolding (config,
DB, alembic, exception handler, dependables); copy those idioms, don't re-derive.

## Responsibilities

- Push events to online users over **SSE** (`text/event-stream`, `GET /events`).
- Fall back to **Firebase Cloud Messaging** when the user has no live SSE
  connection (offline / backgrounded).
- Persist notification history + read-state, and per-user FCM device tokens.
- Validate the same JWT `auth` issues (shared `JWT_SECRET_KEY`, HS256,
  `sub == user_id`). It never issues tokens — `TokenVerifier` only verifies.

## Two Redis roles + one broker — don't conflate

- **RabbitMQ** (`aio-pika`) = durable producer→service broker. Emitters (`chat`,
  admin) publish `NotificationEvent` to topic exchange `nexchat.notifications`;
  the service drains durable queue `notifications.emit`. Survives downtime,
  load-balances across replicas.
- **Redis pub/sub** (`notif:events:{user_id}`) = ephemeral per-user fan-out from
  the emit pipeline to whichever instance holds that user's SSE socket.
- **Redis set** (`notif:online:{user_id}`) = presence, populated on SSE connect
  (mirrors chat's `ConnectionManager`, multi-device).

## Delivery pipeline (`NotificationService.emit`)

`emit` is the single delivery path. The RabbitMQ consumer runs it per message;
the manual `POST /notifications` reaches it by publishing to the same broker
(never inline). Per event: persist the row → if `presence.is_online` publish to
the event bus, else FCM-send to the user's device tokens and prune any FCM
reports unregistered.

## Key files

| File | Purpose |
|---|---|
| `core/notifications/model.py` | `Notification`, `DeviceToken` domain entities |
| `core/notifications/schemas.py` | DTOs + `NotificationEvent` (broker wire object) |
| `core/notifications/service.py` | `emit` pipeline, history, device register/unregister |
| `core/notifications/repository.py` | Ports: repos + `Presence`/`EventBus`/`NotificationBroker`/`PushSender` |
| `core/notifications/security.py` | `TokenVerifier` (copied from chat) |
| `core/notifications/exceptions.py` | Domain exceptions |
| `infra/database/models.py` | `NotificationORM`, `DeviceTokenORM` |
| `infra/database/repositories.py` | SqlAlchemy repo impls |
| `infra/redis/presence.py` | `RedisPresence` (SSE presence set) |
| `infra/redis/pubsub.py` | `RedisEventBus` (per-user pub/sub) |
| `infra/broker/broker.py` | `RabbitMQBroker` (publish + run_consumer) |
| `infra/fcm/client.py` | `FirebasePushSender` (creds from `FCM_CREDENTIALS_FILE`, per-platform message, prune) |
| `infra/web/router.py` | Routes (see below) |
| `infra/web/sse.py` | SSE endpoint + `stream_events` generator |
| `infra/web/dependables.py` | DI; `get_current_user_id` returns the JWT `sub` |
| `runner/consumer.py` | Broker consumer handler (session per event) |
| `runner/setup.py` | `create_app`; lifespan starts/stops the consumer task |

## Endpoints (mounted at root; nginx strips `/api/notifications`)

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/events?token=<jwt>` | query token | SSE; `EventSource` can't set headers |
| POST | `/notifications` | `X-Service-Token` | Producer-only enqueue → 202 (publishes to broker) |
| GET | `/notifications` | Bearer | Caller's history, newest first |
| POST | `/notifications/{id}/read` | Bearer | Own only (403 on IDOR) |
| POST | `/devices` | Bearer | Register FCM token → 201 |
| DELETE | `/devices/{token}` | Bearer | Own only (403 on IDOR) |
| GET | `/health` | none | Healthcheck |

## SSE handshake

Token rides `?token=` (like chat's WS). A bad/expired/wrong-type token is a plain
**HTTP 401** with the `{code, message}` body — SSE has no WS close codes; the
frontend does refresh-once-then-reconnect on 401. `stream_events` registers
presence, relays each published frame, and unregisters in `finally`.

## Error contract

Standard `{"code": "<snake_case>", "message": "..."}` — see `.claude/TESTING.md`.
Catalog pinned in `tests/web/test_exception_mapping.py`
(`notification_not_found` 404, `device_token_not_found` 404, `not_authorized`
403, `token_expired`/`token_invalid`/`not_authenticated` 401).

## Config (`core/config.py`)

Required env: `DATABASE_URL`, `REDIS_URL`, `RABBITMQ_URL`, `JWT_SECRET_KEY`.
Optional: `SERVICE_TOKEN` (trusted-producer secret for `POST /notifications`;
empty → that HTTP path is disabled, broker stays the only producer route),
`FCM_CREDENTIALS_FILE` (path to a gitignored service-account JSON file; empty or
missing → offline push is a no-op), `sse_keepalive_seconds`
(default 15).

`POST /notifications` is authorized by `X-Service-Token`, **not** a user JWT: the
recipient is an arbitrary `user_id`, so a user Bearer would let anyone spoof
notifications to any user (IDOR). Only trusted producers hold the token.

## Tests

Full pyramid under `tests/` (unit/integration/web/api/sse). `FakeBroker` runs the
pipeline synchronously on publish so an API `POST /notifications` persists + routes
without real RabbitMQ; `FakePresence`/`FakeEventBus`/`FakePush` stand in for the
other ports. SSE is tested by driving the `stream_events` generator directly
(sync streaming over ASGITransport isn't supported).

## Follow-ups (not in this service)

- `chat` should publish a `NotificationEvent` to the broker on new message
  (preferred), or call `POST /notifications` with the `X-Service-Token`.
- Frontend `EventSource` client mirroring `core/ws.ts` (401 refresh-reconnect).
