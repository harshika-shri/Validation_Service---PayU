from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.data.repositories.po_resolution.invoice_line_po_allocation_repository import (
    InvoiceLinePOAllocationRepository,
)
from src.data.repositories.po_resolution.po_line_quantity_repository import (
    POLineQuantityRepository,
)


class AllocationLifecycleService:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._allocation_repo = InvoiceLinePOAllocationRepository(
            session,
        )
        self._po_line_quantity_repo = POLineQuantityRepository(
            session,
        )

    async def commit_allocations(
        self,
        invoice_id: UUID,
    ) -> list[UUID]:
        po_line_ids = (
            await self._allocation_repo.commit_pending_for_invoice(
                invoice_id,
            )
        )

        await self._po_line_quantity_repo.recompute_consumed_quantities(
            po_line_ids,
        )

        return po_line_ids

    async def cancel_allocations(
        self,
        invoice_id: UUID,
    ) -> None:
        await self._allocation_repo.cancel_pending_for_invoice(
            invoice_id,
        )
