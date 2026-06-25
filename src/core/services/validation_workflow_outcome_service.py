from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.workflow.validation_event_mapping import (
    ValidationWorkflowEvent,
    map_decision_to_workflow_event,
)
from src.data.models.postgres.enums import (
    InvoiceValidationDecision,
)
from src.data.repositories.invoice_header_resolution.invoice_repository import (
    InvoiceRepository,
)
from src.messaging.redis_stream_publisher import (
    queue_validation_event,
)


class ValidationWorkflowOutcomeService:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session
        self.invoice_repo = InvoiceRepository(
            session,
        )

    async def finalize_and_publish(
        self,
        *,
        invoice_id: UUID,
        decision: InvoiceValidationDecision,
    ) -> ValidationWorkflowEvent:
        workflow_event = map_decision_to_workflow_event(
            decision,
        )

        await self.invoice_repo.update_validation_outcome(
            invoice_id=invoice_id,
            validation_outcome=workflow_event.validation_outcome,
        )

        queue_validation_event(
            invoice_id=invoice_id,
            event_type=workflow_event.event_type,
        )

        return workflow_event
