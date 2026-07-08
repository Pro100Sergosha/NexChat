import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

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
    from app.runner.consumer import run_consumer

    logger.info("notifications service startup")
    consumer_task = asyncio.create_task(run_consumer())
    try:
        yield
    finally:
        consumer_task.cancel()
        with suppress(asyncio.CancelledError):
            await consumer_task
        await engine.dispose()
        await redis_client.aclose()
        logger.info("notifications service shutdown")


def create_app() -> FastAPI:
    configure_logging(settings.LOG_LEVEL)
    app = FastAPI(title="NexChat Notifications", lifespan=lifespan)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(router)
    register_exception_handlers(app)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
