from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, update

from src.data.models.postgres.enums import (
    AllocationMatchType,
    AllocationStatus,
    InvoiceStatus,
)
from src.data.models.postgres.invoice_line_items import InvoiceLineItem
from src.data.models.postgres.invoice_line_po_allocations import (
    InvoiceLinePOAllocation,
)
from src.data.models.postgres.invoices import Invoice
from src.data.models.postgres.po_line_items import POLineItem
from src.data.repositories.base_repo import BaseRepository


@dataclass(frozen=True, slots=True)
class AllocationCreate:
    invoice_line_item_id: UUID
    po_id: UUID
    po_line_item_id: UUID
    allocated_quantity: Decimal
    allocated_amount: Decimal
    match_type: AllocationMatchType


@dataclass(frozen=True, slots=True)
class AllocationRecord:
    invoice_line_item_id: UUID
    po_id: UUID
    po_line_item_id: UUID
    allocated_quantity: Decimal
    allocated_amount: Decimal


class InvoiceLinePOAllocationRepository(BaseRepository):
    async def get_by_invoice_id(
        self,
        invoice_id: UUID,
    ) -> list[AllocationRecord]:
        stmt = (
            select(
                InvoiceLinePOAllocation.invoice_line_item_id,
                InvoiceLinePOAllocation.po_id,
                InvoiceLinePOAllocation.po_line_item_id,
                InvoiceLinePOAllocation.allocated_quantity,
                InvoiceLinePOAllocation.allocated_amount,
            )
            .join(
                InvoiceLineItem,
                InvoiceLineItem.id
                == InvoiceLinePOAllocation.invoice_line_item_id,
            )
            .where(
                InvoiceLineItem.invoice_id == invoice_id,
                InvoiceLinePOAllocation.allocation_status.in_(
                    (
                        AllocationStatus.PENDING.value,
                        AllocationStatus.COMMITTED.value,
                    ),
                ),
            )
        )

        result = await self.execute(
            stmt,
        )

        return [
            AllocationRecord(
                invoice_line_item_id=row.invoice_line_item_id,
                po_id=row.po_id,
                po_line_item_id=row.po_line_item_id,
                allocated_quantity=row.allocated_quantity,
                allocated_amount=row.allocated_amount,
            )
            for row in result.all()
        ]

    async def create_allocation(
        self,
        allocation: AllocationCreate,
    ) -> None:
        await self.create_allocations_bulk(
            [allocation],
        )

    async def create_allocations_bulk(
        self,
        allocations: list[AllocationCreate],
    ) -> None:
        for allocation in allocations:
            record = InvoiceLinePOAllocation(
                invoice_line_item_id=allocation.invoice_line_item_id,
                po_id=allocation.po_id,
                po_line_item_id=allocation.po_line_item_id,
                allocated_quantity=allocation.allocated_quantity,
                allocated_amount=allocation.allocated_amount,
                match_type=allocation.match_type,
                match_confidence=None,
                is_confirmed=True,
                allocation_status=AllocationStatus.PENDING.value,
            )
            self.session.add(
                record,
            )

        if allocations:
            await self.session.flush()

    async def replace_pending_allocations_for_invoice(
        self,
        invoice_id: UUID,
        allocations: list[AllocationCreate],
    ) -> None:
        await self.cancel_pending_for_invoice(
            invoice_id,
        )
        await self.create_allocations_bulk(
            allocations,
        )

    async def get_pending_quantity(
        self,
        po_line_item_id: UUID,
        *,
        exclude_invoice_id: UUID | None = None,
    ) -> Decimal:
        return await self._sum_allocated_quantity(
            po_line_item_id=po_line_item_id,
            allocation_status=AllocationStatus.PENDING,
            exclude_invoice_id=exclude_invoice_id,
        )

    async def get_committed_quantity(
        self,
        po_line_item_id: UUID,
    ) -> Decimal:
        return await self._sum_allocated_quantity(
            po_line_item_id=po_line_item_id,
            allocation_status=AllocationStatus.COMMITTED,
            exclude_invoice_id=None,
        )

    async def get_available_quantity(
        self,
        po_line_item_id: UUID,
        quantity_ordered: Decimal,
        *,
        exclude_invoice_id: UUID | None = None,
    ) -> Decimal:
        committed = await self.get_committed_quantity(
            po_line_item_id,
        )
        pending = await self.get_pending_quantity(
            po_line_item_id,
            exclude_invoice_id=exclude_invoice_id,
        )
        available = quantity_ordered - committed - pending

        return max(
            available.quantize(
                Decimal("0.001"),
            ),
            Decimal(0),
        )

    async def get_available_quantities(
        self,
        po_line_item_ids: list[UUID],
        quantity_ordered_by_id: dict[UUID, Decimal],
        *,
        exclude_invoice_id: UUID | None = None,
    ) -> dict[UUID, Decimal]:
        if not po_line_item_ids:
            return {}

        committed_by_line = await self._sum_allocated_by_po_lines(
            po_line_item_ids=po_line_item_ids,
            allocation_status=AllocationStatus.COMMITTED,
            exclude_invoice_id=None,
        )
        pending_by_line = await self._sum_allocated_by_po_lines(
            po_line_item_ids=po_line_item_ids,
            allocation_status=AllocationStatus.PENDING,
            exclude_invoice_id=exclude_invoice_id,
        )

        available: dict[UUID, Decimal] = {}

        for po_line_item_id in po_line_item_ids:
            ordered = quantity_ordered_by_id.get(
                po_line_item_id,
                Decimal(0),
            )
            committed = committed_by_line.get(
                po_line_item_id,
                Decimal(0),
            )
            pending = pending_by_line.get(
                po_line_item_id,
                Decimal(0),
            )
            quantity = ordered - committed - pending
            available[po_line_item_id] = max(
                quantity.quantize(
                    Decimal("0.001"),
                ),
                Decimal(0),
            )

        return available

    async def commit_pending_for_invoice(
        self,
        invoice_id: UUID,
    ) -> list[UUID]:
        return await self._update_pending_status_for_invoice(
            invoice_id=invoice_id,
            new_status=AllocationStatus.COMMITTED,
        )

    async def cancel_pending_for_invoice(
        self,
        invoice_id: UUID,
    ) -> list[UUID]:
        return await self._update_pending_status_for_invoice(
            invoice_id=invoice_id,
            new_status=AllocationStatus.CANCELLED,
        )

    async def _update_pending_status_for_invoice(
        self,
        invoice_id: UUID,
        new_status: AllocationStatus,
    ) -> list[UUID]:
        pending_allocation_ids = (
            select(
                InvoiceLinePOAllocation.id,
            )
            .join(
                InvoiceLineItem,
                InvoiceLineItem.id
                == InvoiceLinePOAllocation.invoice_line_item_id,
            )
            .where(
                InvoiceLineItem.invoice_id == invoice_id,
                InvoiceLinePOAllocation.allocation_status
                == AllocationStatus.PENDING.value,
            )
        )

        stmt = (
            update(
                InvoiceLinePOAllocation,
            )
            .where(
                InvoiceLinePOAllocation.id.in_(
                    pending_allocation_ids,
                ),
            )
            .values(
                allocation_status=new_status.value,
            )
            .returning(
                InvoiceLinePOAllocation.po_line_item_id,
            )
        )

        result = await self.execute(
            stmt,
        )

        return list(
            {
                row.po_line_item_id
                for row in result.all()
            },
        )

    async def _sum_allocated_quantity(
        self,
        po_line_item_id: UUID,
        allocation_status: AllocationStatus,
        exclude_invoice_id: UUID | None,
    ) -> Decimal:
        stmt = (
            select(
                func.coalesce(
                    func.sum(
                        InvoiceLinePOAllocation.allocated_quantity,
                    ),
                    0,
                ),
            )
            .where(
                InvoiceLinePOAllocation.po_line_item_id
                == po_line_item_id,
                InvoiceLinePOAllocation.allocation_status
                == allocation_status.value,
            )
        )

        # PENDING allocations: exclude both the invoice being re-validated and
        # any invoice that has already been REJECTED (rejected invoices must not
        # consume PO remaining quantity).
        # COMMITTED allocations only need the exclude_invoice_id guard.
        needs_line_join = (
            exclude_invoice_id is not None
            or allocation_status == AllocationStatus.PENDING
        )

        if needs_line_join:
            stmt = stmt.join(
                InvoiceLineItem,
                InvoiceLineItem.id
                == InvoiceLinePOAllocation.invoice_line_item_id,
            )
            if exclude_invoice_id is not None:
                stmt = stmt.where(
                    InvoiceLineItem.invoice_id != exclude_invoice_id,
                )

        if allocation_status == AllocationStatus.PENDING:
            stmt = stmt.join(
                Invoice,
                Invoice.id == InvoiceLineItem.invoice_id,
            ).where(
                Invoice.invoice_status != InvoiceStatus.REJECTED,
            )

        result = await self.execute(
            stmt,
        )
        total = result.scalar_one()

        return Decimal(
            str(total),
        ).quantize(
            Decimal("0.001"),
        )

    async def _sum_allocated_by_po_lines(
        self,
        po_line_item_ids: list[UUID],
        allocation_status: AllocationStatus,
        exclude_invoice_id: UUID | None,
    ) -> dict[UUID, Decimal]:
        stmt = (
            select(
                InvoiceLinePOAllocation.po_line_item_id,
                func.coalesce(
                    func.sum(
                        InvoiceLinePOAllocation.allocated_quantity,
                    ),
                    0,
                ),
            )
            .where(
                InvoiceLinePOAllocation.po_line_item_id.in_(
                    po_line_item_ids,
                ),
                InvoiceLinePOAllocation.allocation_status
                == allocation_status.value,
            )
            .group_by(
                InvoiceLinePOAllocation.po_line_item_id,
            )
        )

        # PENDING allocations: exclude both the re-validated invoice and any
        # invoice that has already been REJECTED — same logic as
        # _sum_allocated_quantity.
        needs_line_join = (
            exclude_invoice_id is not None
            or allocation_status == AllocationStatus.PENDING
        )

        if needs_line_join:
            stmt = stmt.join(
                InvoiceLineItem,
                InvoiceLineItem.id
                == InvoiceLinePOAllocation.invoice_line_item_id,
            )
            if exclude_invoice_id is not None:
                stmt = stmt.where(
                    InvoiceLineItem.invoice_id != exclude_invoice_id,
                )

        if allocation_status == AllocationStatus.PENDING:
            stmt = stmt.join(
                Invoice,
                Invoice.id == InvoiceLineItem.invoice_id,
            ).where(
                Invoice.invoice_status != InvoiceStatus.REJECTED,
            )

        result = await self.execute(
            stmt,
        )

        return {
            row.po_line_item_id: Decimal(
                str(row[1]),
            ).quantize(
                Decimal("0.001"),
            )
            for row in result.all()
        }

    async def recompute_consumed_quantities(
        self,
        po_line_item_ids: list[UUID],
    ) -> None:
        if not po_line_item_ids:
            return

        committed_by_line = await self._sum_allocated_by_po_lines(
            po_line_item_ids=po_line_item_ids,
            allocation_status=AllocationStatus.COMMITTED,
            exclude_invoice_id=None,
        )

        for po_line_item_id in po_line_item_ids:
            consumed = committed_by_line.get(
                po_line_item_id,
                Decimal(0),
            )
            stmt = (
                select(
                    POLineItem,
                )
                .where(
                    POLineItem.id == po_line_item_id,
                )
                .with_for_update()
            )
            result = await self.execute(
                stmt,
            )
            po_line = result.scalar_one_or_none()

            if po_line is None:
                continue

            po_line.consumed_quantity = consumed
