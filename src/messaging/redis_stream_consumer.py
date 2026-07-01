from __future__ import annotations

import asyncio
import logging
from typing import Any

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError, ResponseError, TimeoutError

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
from src.messaging.validation_task_dispatcher import (
    enqueue_invoice_validation,
)

logger = logging.getLogger(
    "validation.messaging",
)


class RedisStreamConsumer:
    def __init__(
        self,
    ) -> None:
        self._redis: Redis | None = None
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._startup_recovery_pending = True
        self._in_flight_stream_messages: set[str] = set()

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
            "Consumer started stream=%s group=%s consumer=%s",
            settings.REDIS_STREAM_NAME,
            settings.REDIS_STREAM_CONSUMER_GROUP,
            settings.REDIS_STREAM_CONSUMER_NAME,
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
        await self._ensure_consumer_group()
        await self._recover_undelivered_stream_entries()

        logger.info(
            "Redis connected host=%s port=%s db=%s stream=%s group=%s consumer=%s",
            settings.REDIS_HOST,
            settings.REDIS_PORT,
            settings.REDIS_DB,
            settings.REDIS_STREAM_NAME,
            settings.REDIS_STREAM_CONSUMER_GROUP,
            settings.REDIS_STREAM_CONSUMER_NAME,
        )

    async def _ensure_consumer_group(
        self,
    ) -> None:
        if self._redis is None:
            raise RuntimeError(
                "Redis client is not initialized.",
            )

        try:
            await self._redis.xgroup_create(
                name=settings.REDIS_STREAM_NAME,
                groupname=settings.REDIS_STREAM_CONSUMER_GROUP,
                id="0",
                mkstream=True,
            )
            logger.info(
                "Created Redis consumer group=%s stream=%s",
                settings.REDIS_STREAM_CONSUMER_GROUP,
                settings.REDIS_STREAM_NAME,
            )
        except ResponseError as error:
            if "BUSYGROUP" not in str(
                error,
            ):
                raise

    async def _recover_undelivered_stream_entries(
        self,
    ) -> None:
        if self._redis is None:
            return

        try:
            stream_info = await self._redis.xinfo_stream(
                settings.REDIS_STREAM_NAME,
            )
            groups = await self._redis.xinfo_groups(
                settings.REDIS_STREAM_NAME,
            )
        except ResponseError:
            return

        group_info = next(
            (
                group
                for group in groups
                if group.get("name")
                == settings.REDIS_STREAM_CONSUMER_GROUP
            ),
            None,
        )

        if group_info is None:
            return

        entries_read = int(
            group_info.get(
                "entries-read",
                0,
            )
            or 0,
        )
        stream_length = int(
            stream_info.get(
                "length",
                0,
            )
            or 0,
        )

        if entries_read >= stream_length:
            return

        reset_id = "0-0"

        logger.warning(
            "Recovering undelivered extraction events "
            "entries_read=%s stream_length=%s reset_id=%s",
            entries_read,
            stream_length,
            reset_id,
        )

        await self._redis.xgroup_setid(
            settings.REDIS_STREAM_NAME,
            settings.REDIS_STREAM_CONSUMER_GROUP,
            reset_id,
        )

        logger.info(
            "Consumer group read position synced for catch-up stream=%s group=%s",
            settings.REDIS_STREAM_NAME,
            settings.REDIS_STREAM_CONSUMER_GROUP,
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

    async def _consume_batch(
        self,
    ) -> None:
        while True:
            processed_pending = await self._read_and_process_messages(
                stream_id="0",
                block_ms=None,
                recovery=self._startup_recovery_pending,
            )

            if not processed_pending:
                self._startup_recovery_pending = False
                break

        await self._read_and_process_messages(
            stream_id=">",
            block_ms=settings.REDIS_STREAM_BLOCK_MS,
            recovery=False,
        )

    async def _read_and_process_messages(
        self,
        *,
        stream_id: str,
        block_ms: int | None,
        recovery: bool,
    ) -> bool:
        if self._redis is None:
            raise RuntimeError(
                "Redis client is not initialized.",
            )

        try:
            read_kwargs: dict[str, object] = {
                "groupname": settings.REDIS_STREAM_CONSUMER_GROUP,
                "consumername": settings.REDIS_STREAM_CONSUMER_NAME,
                "streams": {
                    settings.REDIS_STREAM_NAME: stream_id,
                },
                "count": settings.REDIS_STREAM_BATCH_SIZE,
            }

            if block_ms is not None:
                read_kwargs["block"] = block_ms

            messages = await self._redis.xreadgroup(
                **read_kwargs,
            )
        except TimeoutError:
            return False

        if not messages:
            return False

        entry_count = sum(
            len(entries) for _, entries in messages
        )

        if entry_count == 0:
            return False

        logger.info(
            "Read %s extraction event(s) from stream=%s stream_id=%s",
            entry_count,
            settings.REDIS_STREAM_NAME,
            stream_id,
        )

        for _stream_name, entries in messages:
            for message_id, fields in entries:
                if recovery:
                    logger.info(
                        "Pending message recovered after restart stream=%s "
                        "message_id=%s",
                        settings.REDIS_STREAM_NAME,
                        message_id,
                    )

                await self._process_message(
                    message_id=message_id,
                    fields=fields,
                )

        return True

    async def _process_message(
        self,
        *,
        message_id: str,
        fields: dict[str, Any],
    ) -> None:
        if self._redis is None:
            return

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
            await self._acknowledge_message(
                message_id=message_id,
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
            await self._acknowledge_message(
                message_id=message_id,
            )
            return

        if message_id in self._in_flight_stream_messages:
            logger.info(
                "Extraction event already dispatched; waiting for worker ack "
                "stream=%s message_id=%s invoice_id=%s",
                settings.REDIS_STREAM_NAME,
                message_id,
                payload.invoice_id,
            )
            return

        self._in_flight_stream_messages.add(
            message_id,
        )

        try:
            enqueue_invoice_validation(
                payload.invoice_id,
                stream_message_id=message_id,
                skip_if_already_completed=True,
            )
        except Exception:
            self._in_flight_stream_messages.discard(
                message_id,
            )
            logger.exception(
                "Failed to enqueue validation task stream=%s message_id=%s "
                "invoice_id=%s",
                settings.REDIS_STREAM_NAME,
                message_id,
                payload.invoice_id,
            )
            raise

    async def _acknowledge_message(
        self,
        *,
        message_id: str,
        invoice_id: str | None = None,
    ) -> None:
        if self._redis is None:
            return

        await self._redis.xack(
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
