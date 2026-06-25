from __future__ import annotations

import asyncio
import logging

from redis.asyncio import Redis

from src.config.settings import settings
from src.constants.extraction_event_constants import (
    EXTRACTION_EVENT_COMPLETED,
)
from src.data.clients.redis_client import (
    close_redis_client,
    get_redis_client,
)
from src.tasks.validation_tasks import (
    validate_invoice,
)

logger = logging.getLogger(
    __name__,
)


class ExtractionStreamConsumer:
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

        self._redis = get_redis_client()
        self._running = True
        self._task = asyncio.create_task(
            self._consume_loop(),
        )

        logger.info(
            "Extraction stream consumer started stream=%s",
            settings.EXTRACTION_EVENTS_STREAM,
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

        await close_redis_client()
        self._redis = None

        logger.info(
            "Extraction stream consumer stopped",
        )

    async def _consume_loop(
        self,
    ) -> None:
        if self._redis is None:
            raise RuntimeError(
                "Redis client is not initialized.",
            )

        while self._running:
            try:
                messages = await self._redis.xread(
                    {
                        settings.EXTRACTION_EVENTS_STREAM: self._last_id,
                    },
                    block=settings.REDIS_STREAM_BLOCK_MS,
                    count=10,
                )
            except Exception:
                logger.exception(
                    "Extraction stream read failed stream=%s",
                    settings.EXTRACTION_EVENTS_STREAM,
                )
                await asyncio.sleep(
                    1,
                )
                continue

            if not messages:
                continue

            for _stream_name, entries in messages:
                for message_id, fields in entries:
                    self._last_id = message_id
                    await self._handle_message(
                        fields,
                    )

    async def _handle_message(
        self,
        fields: dict[str, str],
    ) -> None:
        event_type = fields.get(
            "event_type",
        )

        if event_type != EXTRACTION_EVENT_COMPLETED:
            logger.info(
                "Skipping unsupported extraction event event_type=%s",
                event_type,
            )
            return

        invoice_id = fields.get(
            "invoice_id",
        )

        if not invoice_id:
            logger.warning(
                "Skipping extraction event without invoice_id fields=%s",
                fields,
            )
            return

        task = validate_invoice.delay(
            invoice_id=invoice_id,
        )

        logger.info(
            "Validation task enqueued from extraction event "
            "invoice_id=%s task_id=%s event_type=%s stream=%s",
            invoice_id,
            task.id,
            event_type,
            settings.EXTRACTION_EVENTS_STREAM,
        )
