from __future__ import annotations

import logging

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from src.config.settings import settings

logger = logging.getLogger(__name__)

_pool: AsyncConnectionPool | None = None
_checkpointer: AsyncPostgresSaver | None = None
_initialized = False

_PSYCOPG_CONNECTION_KWARGS = {
    "autocommit": True,
    "prepare_threshold": None,
}


def build_psycopg_conninfo() -> str:
    database_url = settings.DATABASE_URL or ""

    if database_url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + database_url.removeprefix(
            "postgresql+asyncpg://",
        )

    if database_url.startswith("postgresql://"):
        return database_url

    return (
        f"postgresql://{settings.POSTGRES_USER}:"
        f"{settings.POSTGRES_PASSWORD}@"
        f"{settings.POSTGRES_HOST}:"
        f"{settings.POSTGRES_PORT}/"
        f"{settings.POSTGRES_DB}"
    )


def reset_checkpointer_globals() -> None:
    global _pool, _checkpointer, _initialized

    _pool = None
    _checkpointer = None
    _initialized = False


async def init_validation_checkpointer() -> AsyncPostgresSaver:
    global _pool, _checkpointer, _initialized

    if _checkpointer is not None and _initialized:
        return _checkpointer

    conninfo = build_psycopg_conninfo()
    _pool = AsyncConnectionPool(
        conninfo=conninfo,
        kwargs=_PSYCOPG_CONNECTION_KWARGS,
        max_size=5,
        open=False,
        timeout=30,
    )
    await _pool.open()

    _checkpointer = AsyncPostgresSaver(_pool)
    await _checkpointer.setup()
    _initialized = True

    logger.info(
        "LangGraph PostgreSQL checkpointer initialized",
        extra={
            "postgres_host": settings.POSTGRES_HOST,
            "postgres_db": settings.POSTGRES_DB,
        },
    )

    return _checkpointer


async def get_validation_checkpointer() -> AsyncPostgresSaver:
    if _checkpointer is None or not _initialized:
        return await init_validation_checkpointer()

    return _checkpointer


async def shutdown_validation_checkpointer() -> None:
    global _pool, _checkpointer, _initialized

    if _pool is not None:
        try:
            await _pool.close()
        except Exception:
            logger.exception(
                "Error closing LangGraph checkpointer pool",
            )

    reset_checkpointer_globals()

    logger.info("LangGraph PostgreSQL checkpointer shut down")
