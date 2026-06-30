from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.infra.database.config import engine
from app.infra.redis.config import redis_client
from app.infra.web.responses import register_exception_handlers
from app.infra.web.router import router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()
    await redis_client.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title="NexChat Auth", lifespan=lifespan)
    app.include_router(router)
    register_exception_handlers(app)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
