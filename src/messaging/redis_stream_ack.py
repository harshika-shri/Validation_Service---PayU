from __future__ import annotations

import logging

import redis

from src.config.settings import settings

logger = logging.getLogger(
    "validation.messaging",
)

_client: redis.Redis | None = None


def _get_client() -> redis.Redis:
    global _client

    if _client is None:
        _client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True,
        )

    return _client


def acknowledge_extraction_stream_message(
    *,
    message_id: str,
    invoice_id: str | None = None,
) -> None:
    client = _get_client()
    client.xack(
        settings.REDIS_STREAM_NAME,
        settings.REDIS_STREAM_CONSUMER_GROUP,
        message_id,
    )

    logger.info(
        "Redis message acknowledged stream=%s message_id=%s invoice_id=%s",
        settings.REDIS_STREAM_NAME,
        message_id,
        invoice_id,
    )
