# Backend Code Style

Conventions shared by every backend service (`auth`, `chat`). Write new code to
match this without reading existing files for reference. Layer boundaries live in
`.claude/RULES.md`; this doc is about *how the code inside each layer reads*.

## Tooling

- Python `>=3.12`, managed with `uv` (`pyproject.toml` per service, `dev`
  dependency-group for pytest/ruff).
- Ruff is the only linter/formatter. `target-version = "py312"`, `line-length = 88`.
- Lint select: `["E", "F", "W", "I", "N", "UP", "B", "SIM", "TCH"]`, `ignore = ["B008"]`
  (B008 off because FastAPI `Depends()` in defaults is intentional).
- isort: `known-first-party = ["app"]`. Imports are always absolute (`from app.core...`),
  never relative. Grouped stdlib / third-party / `app.*`, sorted.
- pytest: `asyncio_mode = "auto"` (no `@pytest.mark.asyncio`), `testpaths = ["tests"]`.

## Typing

- Full type hints on every function, including `-> None`. No untyped defs.
- Modern syntax only: `X | None` not `Optional[X]`, `dict[str, Any]` not `Dict`,
  `list[...]` not `List`. `from typing import Any, Annotated` as needed.
- `datetime` uses `UTC`: `datetime.now(UTC)`, `from datetime import UTC, datetime`.
- UUIDs are `uuid.UUID` in domain/ORM/schemas; stringified (`str(user.id)`) only
  when crossing into JWT `sub` or other string wire fields.

## Domain layer (`core/<domain>/`)

- **`model.py`** — pure domain entity, no framework deps. Plain class/dataclass
  holding `id`, business fields, `created_at`. Never a SQLAlchemy model.
- **`schemas.py`** — pydantic `BaseModel`. Request/response named `XRequest` /
  `XResponse` (plus wire objects like `TokenPair`, `MessageOut`, `WSSendMessage`).
  Constraints via `Field(min_length=..., max_length=...)`. Response models that
  read off ORM/domain objects set `model_config = ConfigDict(from_attributes=True)`.
  Inline `# TODO:` notes for known-unfinished validation are kept, not deleted.
- **`repository.py`** — `ABC` with `@abstractmethod async def ... -> T | None: ...`
  one-line ellipsis stubs. Interface only; no implementation, no I/O imports.
  Method naming: `get_by_email` / `get_by_id` / `create`. Returns `T | None` for
  lookups (never raises "not found" from the repo — the service decides).
- **`service.py`** — business logic. Constructor injection of repository/security
  interfaces, stored as private `self._users`, `self._blacklist`, etc. Public
  methods are `async`, take primitives (`email: str, password: str`), return
  domain objects or schemas, and `raise SomeError()` on rule violations. Private
  helpers prefixed `_` (`_issue_pair`, `_revoke`). No FastAPI/SQLAlchemy imports.
- **`exceptions.py`** — every domain exception subclasses `AppException`
  (`core/exception.py`), carries class attrs `code = "snake_case"` and
  `message = "Human-readable English sentence"`, plus a one-line docstring.
  Raised with `()` (`raise InvalidCredentials()`). Base has
  `# noqa: N818` since it doesn't end in `Error`.

## Infra layer (`infra/`)

- **`database/models.py`** — SQLAlchemy models suffixed `ORM` (`UserORM`,
  `MessageORM`). Any change → Alembic migration in the same commit (see RULES.md).
- **`database/repositories.py`** — impl class named `SqlAlchemy<Interface>`
  (`SqlAlchemyUserRepository`), ctor takes `AsyncSession` as `self._session`.
  Every method maps ORM → domain via a `@staticmethod _to_domain(orm)` before
  returning; the repo never leaks an ORM object outward. Query with
  `select(...).where(...)` + `scalar_one_or_none()`, or `session.get(Model, pk)`.
- **`redis/`** — implements the repository ABC against a real redis client;
  small, protocol-only (no business logic).
- **`web/handler.py`** — thin async functions `async def name(request, service) -> Schema`.
  They only unpack the request, call one service method, and wrap the result
  (`UserResponse.model_validate(user)`). No decorators, no DB, no branching logic.
- **`web/router.py`** — declares `XDep = Annotated[T, Depends(get_x)]` aliases at
  module top, then thin route functions that delegate to `handler.*`. Status codes
  via `status.HTTP_201_CREATED` etc. Protected routes list `Security(oauth2_scheme)`
  in `dependencies=[...]`. Route funcs contain no logic beyond the `handler` call.
- **`web/responses.py`** — exception→HTTP mapping is a
  `_STATUS_MAP: dict[type[AppException], int]`; a single handler renders
  `{"code": exc.code, "message": exc.message}`. `RequestValidationError` is
  rewritten into the same shape with a field-naming message. Module-private
  helpers prefixed `_`.
- **`web/ws.py`** (chat) — WebSocket protocol only. Validate token → `close(code=...)`
  before `.accept()` on failure; after accept, loop `receive_text()` →
  `model_validate` → service call, mapping domain exceptions to close codes
  (4401/4403/4422). Cleanup in `finally`. No business rules here — those live in
  the service.

## Config

- `core/config.py` — `class Settings(BaseSettings)` with
  `model_config = SettingsConfigDict(env_file=".env", extra="ignore")`, then a
  module-level singleton `settings = Settings()`. Secrets are typed fields with
  no default (`DATABASE_URL: str`); tunables get defaults. Never read `os.environ`
  directly, never hardcode secrets.

## Comments

- Sparse. Explain *why*, not *what*: rotation semantics, single-use tokens,
  ack-before-close ordering, cross-instance presence vs. local sockets. A
  non-obvious ordering constraint gets a real paragraph; obvious code gets none.
- `# TODO:` for known gaps (rate-limiting, email edge cases) — left in place as
  a backlog marker, phrased with the intended approach.