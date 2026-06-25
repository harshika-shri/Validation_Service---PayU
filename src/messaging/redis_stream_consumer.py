from __future__ import annotations

import asyncio
import logging
from typing import Any

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError

from src.config.settings import settings
from src.data.clients.redis_client import (
    close_redis_client,
    get_redis_client,
)
from src.messaging.extraction_event_schema import (
    parse_extraction_completed_event,
)
from src.messaging.extraction_events import (
    EXTRACTION_EVENT_COMPLETED,
)
from src.tasks.validation_tasks import (
    validate_invoice,
)

logger = logging.getLogger(
    "validation.messaging",
)

_STREAM_CURSOR_KEY = "validation:extraction_stream:last_id"


class RedisStreamConsumer:
    def __init__(
        self,
    ) -> None:
        self._redis: Redis | None = None
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._last_id = "0-0"

    async def start(
        self,
    ) -> None:
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(
            self._consume_loop(),
        )

        logger.info(
            "Consumer started stream=%s",
            settings.REDIS_STREAM_NAME,
        )

    async def stop(
        self,
    ) -> None:
        self._running = False

        if self._task is not None:
            self._task.cancel()

            try:
                await self._task
            except asyncio.CancelledError:
                pass

            self._task = None

        await self._disconnect_redis()

        logger.info(
            "Consumer stopped stream=%s",
            settings.REDIS_STREAM_NAME,
        )

    async def _consume_loop(
        self,
    ) -> None:
        while self._running:
            try:
                await self._ensure_redis_connected()
                await self._consume_batch()
            except asyncio.CancelledError:
                raise
            except (
                RedisConnectionError,
                RedisError,
                OSError,
            ) as error:
                logger.warning(
                    "Redis disconnected stream=%s reason=%s",
                    settings.REDIS_STREAM_NAME,
                    error,
                )
                await self._disconnect_redis()
                await asyncio.sleep(
                    1,
                )
            except Exception:
                logger.exception(
                    "Consumer error stream=%s",
                    settings.REDIS_STREAM_NAME,
                )
                await asyncio.sleep(
                    1,
                )

    async def _ensure_redis_connected(
        self,
    ) -> None:
        if self._redis is not None:
            return

        self._redis = get_redis_client()
        self._last_id = await self._load_last_id()

        logger.info(
            "Redis connected host=%s port=%s db=%s stream=%s last_id=%s",
            settings.REDIS_HOST,
            settings.REDIS_PORT,
            settings.REDIS_DB,
            settings.REDIS_STREAM_NAME,
            self._last_id,
        )

    async def _disconnect_redis(
        self,
    ) -> None:
        if self._redis is None:
            return

        await close_redis_client()
        self._redis = None

        logger.warning(
            "Redis disconnected stream=%s",
            settings.REDIS_STREAM_NAME,
        )

    async def _load_last_id(
        self,
    ) -> str:
        if self._redis is None:
            return "0-0"

        stored = await self._redis.get(
            _STREAM_CURSOR_KEY,
        )

        if stored:
            return stored

        return "0-0"

    async def _save_last_id(
        self,
        message_id: str,
    ) -> None:
        if self._redis is None:
            return

        await self._redis.set(
            _STREAM_CURSOR_KEY,
            message_id,
        )

    async def _consume_batch(
        self,
    ) -> None:
        if self._redis is None:
            raise RuntimeError(
                "Redis client is not initialized.",
            )

        messages = await self._redis.xread(
            {
                settings.REDIS_STREAM_NAME: self._last_id,
            },
            block=settings.REDIS_STREAM_BLOCK_MS,
            count=10,
        )

        if not messages:
            return

        for _stream_name, entries in messages:
            for message_id, fields in entries:
                self._last_id = message_id
                await self._save_last_id(
                    message_id,
                )
                self._handle_message(
                    message_id=message_id,
                    fields=fields,
                )

    def _handle_message(
        self,
        *,
        message_id: str,
        fields: dict[str, Any],
    ) -> None:
        normalized_fields = {
            str(
                key,
            ): str(
                value,
            )
            for key, value in fields.items()
        }

        logger.info(
            "Event received stream=%s message_id=%s event_type=%s "
            "invoice_id=%s occurred_at=%s",
            settings.REDIS_STREAM_NAME,
            message_id,
            normalized_fields.get(
                "event_type",
            ),
            normalized_fields.get(
                "invoice_id",
            ),
            normalized_fields.get(
                "occurred_at",
            ),
        )

        event_type = normalized_fields.get(
            "event_type",
        )

        if event_type != EXTRACTION_EVENT_COMPLETED:
            logger.info(
                "Ignoring unsupported event stream=%s event_type=%s",
                settings.REDIS_STREAM_NAME,
                event_type,
            )
            return

        try:
            payload = parse_extraction_completed_event(
                normalized_fields,
            )
        except (
            ValidationError,
            ValueError,
        ) as error:
            logger.error(
                "Invalid payload stream=%s message_id=%s fields=%s reason=%s",
                settings.REDIS_STREAM_NAME,
                message_id,
                normalized_fields,
                error,
            )
            return

        task = validate_invoice.delay(
            invoice_id=str(
                payload.invoice_id,
            ),
        )

        logger.info(
            "Validation task queued stream=%s invoice_id=%s task_id=%s "
            "event_type=%s occurred_at=%s",
            settings.REDIS_STREAM_NAME,
            payload.invoice_id,
            task.id,
            payload.event_type,
            payload.occurred_at.isoformat(),
        )
