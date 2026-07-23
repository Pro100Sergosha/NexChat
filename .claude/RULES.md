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
- Tests first, always: write the failing test (red) before the implementation,
  then make it pass (green). Never write implementation first and back-fill
  tests. See `.claude/TESTING.md` for the full TDD convention.
- Every service logs through stdlib `logging` — a module-level
  `logger = logging.getLogger(__name__)`, never `print`, never a bespoke
  logger. See `.claude/backend/style.md` for levels and what to log where.
- Any non-obvious function gets a docstring explaining *why* / the invariant —
  see the Docstrings section in `.claude/backend/style.md`. When you touch a
  complex function that lacks one, add it as part of the change.
- Always run the linter (`rtk uv run ruff check .` / `rtk uv run ruff format .`) after modifying code to ensure compliance.
- Always prefix all shell/terminal/CLI commands with `rtk` (e.g. `rtk git ...`, `rtk uv ...`, `rtk pytest ...`).

## Delegating complex work to agents

Don't hand-build large or intricate features single-threaded when they can be
decomposed and farmed out. Prefer spawning agents (via `ruflo`) for such work.

- **What to delegate**: multi-file features, whole-layer scaffolding (a new
  `core/<domain>/` + its `infra/` impls + tests), broad refactors, anything that
  fans out into independent, well-scoped subtasks.
- **What to keep inline**: single-file edits, doc tweaks, architectural
  decisions, wiring/merging the agents' output, and final review.
- **Model tier**: these subtasks are mechanical once specified — run the agents
  on a cheaper/weaker model. Spend the strong model on the spec, the decomposition,
  and the integration/review, not on the boilerplate.
- **Always specify the contract up front**: point each agent at `.claude/` (this
  file, `TESTING.md`, `backend/style.md`, the service doc) so its output matches
  conventions. TDD still holds — the agent writes the red test before the impl.
- **You own the merge**: agents produce; you reconcile, run the suite, and don't
  commit anything you haven't reviewed.
- **Question the complexity first**: before delegating a big build, run it past
  the `ponytail` skill — it forces the laziest solution that works (stdlib over a
  dep, native feature over custom code, one line over fifty, or dropping the task
  as YAGNI). Often the "complex" feature shrinks enough to not need agents at all.
  Feed the agents the trimmed scope, not the original over-engineered one.

## When to update .claude/ docs

- New service added → create `.claude/backend/<service>.md` + add @import to CLAUDE.md
- Architecture changes (new Redis usage, new service boundary) → update ARCHITECTURE.md
- New cross-cutting rule → update RULES.md
- Cross-service testing conventions (pyramid layout, error contract, shared fixtures) → update TESTING.md
- Never update CLAUDE.md for content — only for new @imports
