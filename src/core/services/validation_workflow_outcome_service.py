from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.workflow.validation_event_mapping import (
    map_outcome_to_event_type,
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
    ) -> str:
        _ = decision

        validation_outcome = await self.invoice_repo.get_validation_outcome(
            invoice_id,
        )

        if validation_outcome is None:
            raise ValueError(
                f"Validation outcome is missing for invoice {invoice_id}.",
            )

        event_type = map_outcome_to_event_type(
            validation_outcome,
        )

        queue_validation_event(
            invoice_id=invoice_id,
            event_type=event_type,
            validation_outcome=validation_outcome.value,
        )

        return event_type
