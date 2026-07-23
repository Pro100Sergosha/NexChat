# Chat Service

Port: 8001
Framework: FastAPI + SQLAlchemy (async) + Alembic + Redis + WebSockets

## Responsibilities

- WebSocket connection management (ConnectionManager in Redis)
- Sending and storing messages
- Conversation CRUD — both 1:1 and **group** conversations
- Group membership: create named group, add/remove participants (owner-gated)
- JWT validation on WS handshake (verifies signature, checks Redis blacklist via auth service or shared secret)

## Conversation model

A `Conversation` has a **set of participants** (`>= 2` user ids), not a fixed
pair. 1:1 is the degenerate case: exactly two participants, `name = None`,
`is_group = False`. A group has `name`, `is_group = True`, an `owner_id`
(creator), and `>= 2` participants.

- Membership lives in a join table (`ConversationParticipantORM`: `conversation_id`,
  `user_id`) — no participant columns on `Conversation` itself.
- Authorization is uniform: a user may read/send only if they're a participant.
  Non-participant send/read → close/`4403` (WS) or 403 (HTTP). Group vs 1:1 uses
  the same check — membership, not a special-cased pair.
- Owner-only mutations (add/remove participant, rename) → 403 `not_owner` when a
  non-owner attempts them. Removing yourself (leave) is allowed for any member.
- 1:1 conversations are deduped by participant pair (existing behaviour); groups
  are never deduped — a fresh group is always a new row.

## Key files

| File | Purpose |
|---|---|
| `core/chat/model.py` | Message, Conversation domain entities (Conversation carries `participants`, `name`, `is_group`, `owner_id`) |
| `core/chat/schemas.py` | Pydantic schemas for messages/conversations |
| `core/chat/service.py` | Message send, history fetch, conversation management |
| `core/chat/repository.py` | MessageRepository, ConversationRepository interfaces |
| `core/chat/exceptions.py` | Domain exceptions |
| `infra/database/models.py` | SQLAlchemy Message + Conversation + ConversationParticipant models |
| `infra/database/repositories.py` | Repository implementations |
| `infra/redis/` | ConnectionManager: active WS connections per user |
| `infra/web/router.py` | HTTP: GET /conversations, GET /messages/{conv_id}, POST /conversations (create group), POST/DELETE /conversations/{id}/participants (owner-gated), POST /conversations/{id}/leave |
| `infra/web/ws.py` | WebSocket handler only — connect, receive, broadcast, disconnect |
| `infra/web/handler.py` | HTTP endpoint handlers |
| `infra/web/dependables.py` | FastAPI dependencies (get_current_user from JWT) |

## WebSocket flow

1. Client connects: `ws://host/ws?token=<jwt>`
2. Handler validates JWT → extracts user_id
3. ConnectionManager registers connection in Redis
4. Messages received → saved to DB via service → broadcast to **every other
   participant** of the conversation (fan-out over the participant set — same
   path for 1:1 and group; a group just has more recipients)
5. Disconnect → ConnectionManager removes from Redis

An inbound frame addresses either an existing `conversation_id` (1:1 or group)
or, for 1:1 only, a `recipient_id` (get-or-create the pair). A group is never
created over WS — it comes from `POST /conversations` first, then messages
address it by `conversation_id`. Sender must be a participant → else `4403`.
