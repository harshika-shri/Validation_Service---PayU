from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from sqlalchemy import text

from src.api.rest.middleware.cors import add_cors_middleware
from src.api.rest.middleware.error_handler import add_error_handlers
from src.api.rest.routes.health import router as health_router
from src.api.rest.routes.validation import router as validation_router
from src.data.clients.postgres_client import get_or_create_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = get_or_create_engine()

    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))

        print("Database connected")

    except Exception as e:
        print("Database connection failed")
        print(e)

    yield

    await engine.dispose()

    print("Database connections closed")


app = FastAPI(
    title="PayU",
    lifespan=lifespan,
)

add_cors_middleware(app)
add_error_handlers(app)

app.include_router(router=health_router)
app.include_router(router=validation_router)
