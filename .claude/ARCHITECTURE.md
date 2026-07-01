# Architecture

## Overview

Microservices monorepo. Two backend services + static frontend, proxied through Nginx.

```
Client → Nginx → /api/auth/*  → auth  (port 8000)
                → /api/chat/*  → chat  (port 8001)
                → /ws/*        → chat  (port 8001, WebSocket)
                → /*           → frontend (static)
```

## Services

| Service  | Port | Responsibility                                |
|----------|------|-----------------------------------------------|
| auth     | 8000 | JWT issue/refresh/revoke, registration, login |
| chat     | 8001 | WebSocket, messages, conversations            |
| frontend | —    | Static HTML/JS, no SSR                        |

## Data flow

- auth issues JWT → client stores token
- chat validates JWT on WS handshake (verifies signature locally)
- Redis in auth: JWT blacklist (revoked tokens)
- Redis in chat: active WebSocket connections (ConnectionManager)
- Each service has its own Postgres DB — no cross-DB queries

## Folder layout

```
NexChat/
├── backend/
│   ├── auth/   → FastAPI, port 8000
│   └── chat/   → FastAPI, port 8001
├── frontend/   → plain HTML/JS
├── nginx/      → reverse proxy config
└── docker-compose.yml
```

## Layer conventions (per service)

```
app/core/        → domain: models, services, repositories (interfaces), schemas, exceptions
app/infra/       → implementations: DB, Redis, HTTP handlers
app/runner/      → app factory, ASGI entry, startup/shutdown
```
