from __future__ import annotations

import logging
from uuid import UUID

from src.tasks.validation_tasks import validate_invoice

logger = logging.getLogger(
    "validation.messaging",
)


def enqueue_invoice_validation(
    invoice_id: UUID,
    *,
    stream_message_id: str,
    skip_if_already_completed: bool = True,
    force_fresh: bool = False,
) -> str:
    async_result = validate_invoice.apply_async(
        args=[
            str(
                invoice_id,
            ),
        ],
        kwargs={
            "skip_if_already_completed": skip_if_already_completed,
            "force_fresh": force_fresh,
            "stream_message_id": stream_message_id,
        },
    )

    logger.info(
        "Validation task enqueued invoice_id=%s stream_message_id=%s "
        "celery_task_id=%s skip_if_already_completed=%s force_fresh=%s",
        invoice_id,
        stream_message_id,
        async_result.id,
        skip_if_already_completed,
        force_fresh,
    )

    return str(
        async_result.id,
    )
