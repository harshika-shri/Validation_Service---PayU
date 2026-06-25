from __future__ import annotations

import json
import logging
from uuid import UUID

from src.config.settings import settings
from src.core.workflow.validation_event_mapping import (
    ValidationWorkflowEvent,
)
from src.data.clients.redis_client import (
    get_redis_client,
)

logger = logging.getLogger(__name__)

_EVENT_OUTCOME_TO_PAYLOAD = {
    "approved": "APPROVED",
    "pending_review": "PENDING_REVIEW",
    "rejected": "REJECTED",
}


class ValidationEventPublisherService:
    async def publish_validation_event(
        self,
        *,
        invoice_id: UUID,
        workflow_event: ValidationWorkflowEvent,
    ) -> None:
        payload = {
            "invoice_id": str(invoice_id),
            "event_type": workflow_event.event_type,
            "validation_outcome": _EVENT_OUTCOME_TO_PAYLOAD[
                workflow_event.validation_outcome.value
            ],
        }

        redis_client = get_redis_client()
        await redis_client.xadd(
            settings.VALIDATION_EVENTS_STREAM,
            {
                "payload": json.dumps(payload),
            },
        )

        logger.info(
            "Published validation event invoice_id=%s event_type=%s outcome=%s",
            invoice_id,
            workflow_event.event_type,
            workflow_event.validation_outcome.value,
        )
