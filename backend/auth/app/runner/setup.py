import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.infra.database.config import engine
from app.infra.redis.config import redis_client
from app.infra.web.responses import register_exception_handlers
from app.infra.web.router import router
from app.runner.logging import RequestContextMiddleware, configure_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("auth service startup")
    yield
    await engine.dispose()
    await redis_client.aclose()
    logger.info("auth service shutdown")


def create_app() -> FastAPI:
    configure_logging(settings.LOG_LEVEL)
    app = FastAPI(title="NexChat Auth", lifespan=lifespan)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(router)
    register_exception_handlers(app)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
