from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.services.allocation_lifecycle_service import (
    AllocationLifecycleService,
)
from src.core.services.validation_workflow_service import (
    ValidationWorkflowService,
)
from src.schemas.validation_state_schema import (
    ValidationStateSchema,
)


class ValidationService:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session
        self._workflow_service = ValidationWorkflowService(
            session,
        )

    async def validate_invoice(
        self,
        invoice_id: UUID,
    ) -> ValidationStateSchema:
        return await self._workflow_service.run_invoice_validation(
            invoice_id,
        )

    async def commit_invoice_allocations(
        self,
        invoice_id: UUID,
    ) -> None:
        lifecycle_service = AllocationLifecycleService(
            self._session,
        )
        await lifecycle_service.commit_allocations(
            invoice_id,
        )

    async def cancel_invoice_allocations(
        self,
        invoice_id: UUID,
    ) -> None:
        lifecycle_service = AllocationLifecycleService(
            self._session,
        )
        await lifecycle_service.cancel_allocations(
            invoice_id,
        )
