# Chat Service

Port: 8001
Framework: FastAPI + SQLAlchemy (async) + Alembic + Redis + WebSockets

## Responsibilities

- WebSocket connection management (ConnectionManager in Redis)
- Sending and storing messages
- Conversation CRUD
- JWT validation on WS handshake (verifies signature, checks Redis blacklist via auth service or shared secret)

## Key files

| File | Purpose |
|---|---|
| `core/chat/model.py` | Message, Conversation domain entities |
| `core/chat/schemas.py` | Pydantic schemas for messages/conversations |
| `core/chat/service.py` | Message send, history fetch, conversation management |
| `core/chat/repository.py` | MessageRepository, ConversationRepository interfaces |
| `core/chat/exceptions.py` | Domain exceptions |
| `infra/database/models.py` | SQLAlchemy Message + Conversation models |
| `infra/database/repositories.py` | Repository implementations |
| `infra/redis/` | ConnectionManager: active WS connections per user |
| `infra/web/router.py` | HTTP: GET /conversations, GET /messages/{conv_id} |
| `infra/web/ws.py` | WebSocket handler only — connect, receive, broadcast, disconnect |
| `infra/web/handler.py` | HTTP endpoint handlers |
| `infra/web/dependables.py` | FastAPI dependencies (get_current_user from JWT) |

## WebSocket flow

1. Client connects: `ws://host/ws?token=<jwt>`
2. Handler validates JWT → extracts user_id
3. ConnectionManager registers connection in Redis
4. Messages received → saved to DB via service → broadcast to recipients
5. Disconnect → ConnectionManager removes from Redis
