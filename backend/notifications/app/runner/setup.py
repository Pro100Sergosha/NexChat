import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.infra.database.config import engine
from app.infra.redis.config import redis_client
from app.infra.web.responses import register_exception_handlers
from app.infra.web.router import router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Drain the RabbitMQ queue in the background for the app's lifetime. Import
    # lazily so importing the app (tests) never pulls in aio-pika.
    from app.runner.consumer import run_consumer

    consumer_task = asyncio.create_task(run_consumer())
    try:
        yield
    finally:
        consumer_task.cancel()
        with suppress(asyncio.CancelledError):
            await consumer_task
        await engine.dispose()
        await redis_client.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title="NexChat Notifications", lifespan=lifespan)
    app.include_router(router)
    register_exception_handlers(app)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
