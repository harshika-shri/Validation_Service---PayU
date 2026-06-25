from __future__ import annotations

import logging
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import redis

from src.config.settings import settings
from src.messaging.validation_events import (
    VALIDATION_EVENT_VERSION,
)

logger = logging.getLogger(
    "validation.messaging",
)


@dataclass(
    frozen=True,
    slots=True,
)
class PendingValidationEvent:
    invoice_id: UUID
    event_type: str


class RedisStreamPublisher:
    def __init__(
        self,
    ) -> None:
        self._client: redis.Redis | None = None

    def _get_client(
        self,
    ) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True,
            )

        return self._client

    def publish_validation_event(
        self,
        invoice_id: UUID,
        event_type: str,
        *,
        occurred_at: datetime | None = None,
    ) -> str:
        timestamp = occurred_at or datetime.now(
            UTC,
        )
        event_payload = {
            "version": str(
                VALIDATION_EVENT_VERSION,
            ),
            "event_type": event_type,
            "invoice_id": str(
                invoice_id,
            ),
            "occurred_at": timestamp.isoformat(),
        }

        message_id = self._get_client().xadd(
            settings.VALIDATION_EVENTS_STREAM,
            event_payload,
        )

        logger.info(
            "Redis event published stream=%s event_type=%s "
            "invoice_id=%s message_id=%s occurred_at=%s",
            settings.VALIDATION_EVENTS_STREAM,
            event_type,
            invoice_id,
            message_id,
            event_payload[
                "occurred_at"
            ],
        )

        return str(
            message_id,
        )

    def close(
        self,
    ) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None


_publisher: RedisStreamPublisher | None = None


def get_redis_stream_publisher() -> RedisStreamPublisher:
    global _publisher

    if _publisher is None:
        _publisher = RedisStreamPublisher()

    return _publisher


_pending_validation_events: ContextVar[
    list[PendingValidationEvent] | None
] = ContextVar(
    "pending_validation_events",
    default=None,
)


def _get_pending_events() -> list[PendingValidationEvent]:
    pending = _pending_validation_events.get()

    if pending is None:
        pending = []
        _pending_validation_events.set(
            pending,
        )

    return pending


def queue_validation_event(
    invoice_id: UUID,
    event_type: str,
) -> None:
    pending = _get_pending_events()
    event = PendingValidationEvent(
        invoice_id=invoice_id,
        event_type=event_type,
    )

    if event not in pending:
        pending.append(
            event,
        )


def clear_validation_event_buffer() -> None:
    _pending_validation_events.set(
        [],
    )


def flush_validation_events() -> None:
    pending = _get_pending_events()

    if not pending:
        return

    publisher = get_redis_stream_publisher()

    for event in pending:
        logger.info(
            "Validation completed invoice_id=%s event_type=%s",
            event.invoice_id,
            event.event_type,
        )

        try:
            publisher.publish_validation_event(
                event.invoice_id,
                event.event_type,
            )
        except Exception:
            logger.exception(
                "Redis publish failed stream=%s event_type=%s "
                "invoice_id=%s",
                settings.VALIDATION_EVENTS_STREAM,
                event.event_type,
                event.invoice_id,
            )

    _pending_validation_events.set(
        [],
    )
