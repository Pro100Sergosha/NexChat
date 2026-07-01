# Rules for Claude

## When to modify files

| File/Layer | Modify when |
|---|---|
| `core/*/model.py` | domain entity changes only |
| `core/*/schemas.py` | API contract changes (add/remove fields) |
| `core/*/service.py` | business logic changes |
| `core/*/repository.py` | repository interface changes (add method) |
| `infra/database/models.py` | DB schema changes → always create Alembic migration |
| `infra/database/repositories.py` | repository implementation changes |
| `infra/web/router.py` | new endpoint or route change |
| `infra/web/handler.py` | request/response handling logic |
| `infra/web/ws.py` | WebSocket logic only (chat service) |
| `infra/redis/` | Redis interaction changes |
| `runner/` | startup/shutdown, middleware, app factory |

## Hard rules

- Never add business logic to `infra/` layer — it belongs in `core/service.py`
- Never query DB directly from `infra/web/` — go through service → repository
- Never cross DB boundaries between auth and chat services
- Any change to `infra/database/models.py` → create Alembic migration in same commit
- `ws.py` handles only WebSocket protocol — no DB calls directly
- Secrets never hardcoded — always from `core/config.py` (pydantic-settings)

## When to update .claude/ docs

- New service added → create `.claude/backend/<service>.md` + add @import to CLAUDE.md
- Architecture changes (new Redis usage, new service boundary) → update ARCHITECTURE.md
- New cross-cutting rule → update RULES.md
- Never update CLAUDE.md for content — only for new @imports
