from __future__ import annotations

import logging

from redis.asyncio import Redis

from src.config.settings import settings

logger = logging.getLogger(__name__)

_redis_client: Redis | None = None


def get_redis_client() -> Redis:
    global _redis_client

    if _redis_client is None:
        _redis_client = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True,
            socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
        )
        logger.info(
            "Redis client initialized host=%s port=%s db=%s "
            "socket_timeout=%ss block_ms=%s",
            settings.REDIS_HOST,
            settings.REDIS_PORT,
            settings.REDIS_DB,
            settings.REDIS_SOCKET_TIMEOUT_SECONDS,
            settings.REDIS_STREAM_BLOCK_MS,
        )

    return _redis_client


async def close_redis_client() -> None:
    global _redis_client

    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Redis client closed")
