from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.data.repositories.base_repo import BaseRepository
from src.data.repositories.po_resolution.invoice_line_allocation_candidate_repository import (
    InvoiceLineAllocationCandidateRepository,
)
from src.data.repositories.po_resolution.invoice_line_po_allocation_repository import (
    InvoiceLinePOAllocationRepository,
)


class POLineQuantityRepository(BaseRepository):
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        super().__init__(
            session,
        )
        self._allocation_repo = InvoiceLinePOAllocationRepository(
            session,
        )
        self._candidate_repo = InvoiceLineAllocationCandidateRepository(
            session,
        )

    async def get_committed_quantity(
        self,
        po_line_id: UUID,
    ) -> Decimal:
        return await self._allocation_repo.get_committed_quantity(
            po_line_id,
        )

    async def get_pending_quantity(
        self,
        po_line_id: UUID,
        *,
        exclude_invoice_id: UUID | None = None,
    ) -> Decimal:
        return await self._allocation_repo.get_pending_quantity(
            po_line_id,
            exclude_invoice_id=exclude_invoice_id,
        )

    async def get_available_quantity(
        self,
        po_line_id: UUID,
        quantity_ordered: Decimal,
        *,
        exclude_invoice_id: UUID | None = None,
    ) -> Decimal:
        available = await self.get_available_quantities(
            po_line_ids=[po_line_id],
            quantity_ordered_by_id={
                po_line_id: quantity_ordered,
            },
            exclude_invoice_id=exclude_invoice_id,
        )

        return available.get(
            po_line_id,
            Decimal(0),
        )

    async def get_available_quantities(
        self,
        po_line_ids: list[UUID],
        quantity_ordered_by_id: dict[UUID, Decimal],
        *,
        exclude_invoice_id: UUID | None = None,
    ) -> dict[UUID, Decimal]:
        if not po_line_ids:
            return {}

        final_available = (
            await self._allocation_repo.get_available_quantities(
                po_line_item_ids=po_line_ids,
                quantity_ordered_by_id=quantity_ordered_by_id,
                exclude_invoice_id=exclude_invoice_id,
            )
        )
        reserved_by_line = (
            await self._candidate_repo.get_reserved_quantities_by_po_lines(
                po_line_item_ids=po_line_ids,
                exclude_invoice_id=exclude_invoice_id,
            )
        )

        available: dict[UUID, Decimal] = {}

        for po_line_item_id in po_line_ids:
            remaining = final_available.get(
                po_line_item_id,
                Decimal(0),
            ) - reserved_by_line.get(
                po_line_item_id,
                Decimal(0),
            )
            available[po_line_item_id] = max(
                remaining.quantize(
                    Decimal("0.001"),
                ),
                Decimal(0),
            )

        return available

    async def recompute_consumed_quantities(
        self,
        po_line_ids: list[UUID],
    ) -> None:
        await self._allocation_repo.recompute_consumed_quantities(
            po_line_ids,
        )
