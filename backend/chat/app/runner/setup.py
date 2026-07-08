import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.infra.database.config import engine
from app.infra.redis.config import redis_client
from app.infra.web.dependables import get_notification_publisher
from app.infra.web.responses import register_exception_handlers
from app.infra.web.router import router
from app.infra.web.ws import router as ws_router
from app.runner.logging import RequestContextMiddleware, configure_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("chat service startup")
    publisher = get_notification_publisher()
    try:
        await publisher.connect()
    except Exception:
        # Best-effort: a broker down at startup must not stop chat from serving —
        # message notifications are simply dropped until it recovers + restart.
        logger.warning("notification broker connect failed", exc_info=True)
    yield
    await publisher.close()
    await engine.dispose()
    await redis_client.aclose()
    logger.info("chat service shutdown")


def create_app() -> FastAPI:
    configure_logging(settings.LOG_LEVEL)
    app = FastAPI(title="NexChat Chat", lifespan=lifespan)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(router)
    app.include_router(ws_router)
    register_exception_handlers(app)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
