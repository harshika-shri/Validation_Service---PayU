from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.services.validation_event_publisher_service import (
    ValidationEventPublisherService,
)
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


class ValidationWorkflowOutcomeService:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session
        self.invoice_repo = InvoiceRepository(
            session,
        )
        self.event_publisher = ValidationEventPublisherService()

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
        await self._session.commit()
        await self.event_publisher.publish_validation_event(
            invoice_id=invoice_id,
            workflow_event=workflow_event,
        )

        return workflow_event
