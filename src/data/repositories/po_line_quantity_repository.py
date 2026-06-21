from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.data.repositories.base_repo import BaseRepository
from src.data.repositories.invoice_line_po_allocation_repository import (
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
        return await self._allocation_repo.get_available_quantity(
            po_line_id,
            quantity_ordered,
            exclude_invoice_id=exclude_invoice_id,
        )

    async def get_available_quantities(
        self,
        po_line_ids: list[UUID],
        quantity_ordered_by_id: dict[UUID, Decimal],
        *,
        exclude_invoice_id: UUID | None = None,
    ) -> dict[UUID, Decimal]:
        return await self._allocation_repo.get_available_quantities(
            po_line_item_ids=po_line_ids,
            quantity_ordered_by_id=quantity_ordered_by_id,
            exclude_invoice_id=exclude_invoice_id,
        )

    async def recompute_consumed_quantities(
        self,
        po_line_ids: list[UUID],
    ) -> None:
        await self._allocation_repo.recompute_consumed_quantities(
            po_line_ids,
        )
