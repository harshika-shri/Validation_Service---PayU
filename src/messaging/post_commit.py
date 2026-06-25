from __future__ import annotations

from src.messaging.redis_stream_publisher import (
    clear_validation_event_buffer,
    flush_validation_events,
)


def publish_committed_validation_events() -> None:
    flush_validation_events()


def discard_pending_validation_events() -> None:
    clear_validation_event_buffer()
