from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, func, select, update

from src.data.models.postgres.enums import POResolutionCandidateType
from src.data.models.postgres.invoice_line_allocation_candidates import (
    InvoiceLineAllocationCandidateGroup,
    InvoiceLineAllocationCandidateItem,
)
from src.data.models.postgres.po_line_items import POLineItem
from src.data.repositories.base_repo import BaseRepository
from src.data.repositories.po_resolution.invoice_line_po_allocation_repository import (
    AllocationRecord,
)

_RESERVATION_CANDIDATE_TYPES = (
    POResolutionCandidateType.RESOLVED,
    POResolutionCandidateType.RECOVERED,
)


@dataclass(frozen=True, slots=True)
class AllocationCandidateItemCreate:
    invoice_line_item_id: UUID
    po_line_item_id: UUID
    allocated_quantity: Decimal
    allocated_amount: Decimal
    candidate_type: POResolutionCandidateType


@dataclass(frozen=True, slots=True)
class AllocationCandidateGroupCreate:
    resolution_group_id: UUID | None
    candidate_type: POResolutionCandidateType
    items: list[AllocationCandidateItemCreate]
    confidence_score: Decimal | None = None
    is_selected: bool = False


@dataclass(frozen=True, slots=True)
class AllocationCandidateGroupRecord:
    id: UUID
    invoice_id: UUID
    resolution_group_id: UUID | None
    candidate_type: POResolutionCandidateType
    confidence_score: Decimal | None
    is_selected: bool
    items: list[AllocationCandidateItemCreate]


class InvoiceLineAllocationCandidateRepository(BaseRepository):
    async def delete_groups_for_invoice(
        self,
        invoice_id: UUID,
    ) -> None:
        stmt = delete(
            InvoiceLineAllocationCandidateGroup,
        ).where(
            InvoiceLineAllocationCandidateGroup.invoice_id
            == invoice_id,
        )
        await self.execute(stmt)

    async def replace_groups_for_invoice(
        self,
        invoice_id: UUID,
        groups: list[AllocationCandidateGroupCreate],
    ) -> list[AllocationCandidateGroupRecord]:
        await self.delete_groups_for_invoice(
            invoice_id,
        )

        records: list[AllocationCandidateGroupRecord] = []

        for group in groups:
            candidate_group = InvoiceLineAllocationCandidateGroup(
                invoice_id=invoice_id,
                resolution_group_id=group.resolution_group_id,
                candidate_type=group.candidate_type,
                confidence_score=group.confidence_score,
                is_selected=group.is_selected,
            )
            self.session.add(
                candidate_group,
            )
            await self.session.flush()

            for item in group.items:
                self.session.add(
                    InvoiceLineAllocationCandidateItem(
                        allocation_candidate_group_id=candidate_group.id,
                        invoice_line_item_id=item.invoice_line_item_id,
                        po_line_item_id=item.po_line_item_id,
                        allocated_quantity=item.allocated_quantity,
                        allocated_amount=item.allocated_amount,
                        candidate_type=item.candidate_type,
                    ),
                )

            records.append(
                AllocationCandidateGroupRecord(
                    id=candidate_group.id,
                    invoice_id=invoice_id,
                    resolution_group_id=group.resolution_group_id,
                    candidate_type=group.candidate_type,
                    confidence_score=group.confidence_score,
                    is_selected=group.is_selected,
                    items=list(
                        group.items,
                    ),
                ),
            )

        await self.session.flush()
        return records

    async def get_reserved_quantities_by_po_lines(
        self,
        po_line_item_ids: list[UUID],
        *,
        exclude_invoice_id: UUID | None = None,
    ) -> dict[UUID, Decimal]:
        if not po_line_item_ids:
            return {}

        stmt = (
            select(
                InvoiceLineAllocationCandidateItem.po_line_item_id,
                func.coalesce(
                    func.sum(
                        InvoiceLineAllocationCandidateItem.allocated_quantity,
                    ),
                    0,
                ),
            )
            .join(
                InvoiceLineAllocationCandidateGroup,
                InvoiceLineAllocationCandidateGroup.id
                == InvoiceLineAllocationCandidateItem.allocation_candidate_group_id,
            )
            .where(
                InvoiceLineAllocationCandidateItem.po_line_item_id.in_(
                    po_line_item_ids,
                ),
                InvoiceLineAllocationCandidateGroup.candidate_type.in_(
                    _RESERVATION_CANDIDATE_TYPES,
                ),
            )
            .group_by(
                InvoiceLineAllocationCandidateItem.po_line_item_id,
            )
        )

        if exclude_invoice_id is not None:
            stmt = stmt.where(
                InvoiceLineAllocationCandidateGroup.invoice_id
                != exclude_invoice_id,
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

    async def select_group(
        self,
        invoice_id: UUID,
        group_id: UUID,
    ) -> AllocationCandidateGroupRecord | None:
        await self.execute(
            update(
                InvoiceLineAllocationCandidateGroup,
            )
            .where(
                InvoiceLineAllocationCandidateGroup.invoice_id
                == invoice_id,
            )
            .values(
                is_selected=False,
            ),
        )
        await self.execute(
            update(
                InvoiceLineAllocationCandidateGroup,
            )
            .where(
                InvoiceLineAllocationCandidateGroup.id == group_id,
                InvoiceLineAllocationCandidateGroup.invoice_id
                == invoice_id,
            )
            .values(
                is_selected=True,
            ),
        )

        groups = await self.get_groups_for_invoice(
            invoice_id,
        )

        for group in groups:
            if group.id == group_id:
                return group

        return None

    async def get_groups_for_invoice(
        self,
        invoice_id: UUID,
    ) -> list[AllocationCandidateGroupRecord]:
        stmt = (
            select(
                InvoiceLineAllocationCandidateGroup,
            )
            .where(
                InvoiceLineAllocationCandidateGroup.invoice_id
                == invoice_id,
            )
            .order_by(
                InvoiceLineAllocationCandidateGroup.created_at,
            )
        )
        result = await self.execute(
            stmt,
        )
        groups = result.scalars().all()

        records: list[AllocationCandidateGroupRecord] = []

        for group in groups:
            item_stmt = select(
                InvoiceLineAllocationCandidateItem,
            ).where(
                InvoiceLineAllocationCandidateItem.allocation_candidate_group_id
                == group.id,
            )
            item_result = await self.execute(
                item_stmt,
            )
            items = [
                AllocationCandidateItemCreate(
                    invoice_line_item_id=item.invoice_line_item_id,
                    po_line_item_id=item.po_line_item_id,
                    allocated_quantity=item.allocated_quantity,
                    allocated_amount=item.allocated_amount,
                    candidate_type=item.candidate_type,
                )
                for item in item_result.scalars().all()
            ]
            records.append(
                AllocationCandidateGroupRecord(
                    id=group.id,
                    invoice_id=group.invoice_id,
                    resolution_group_id=group.resolution_group_id,
                    candidate_type=group.candidate_type,
                    confidence_score=group.confidence_score,
                    is_selected=group.is_selected,
                    items=items,
                ),
            )

        return records

    async def get_selected_group(
        self,
        invoice_id: UUID,
    ) -> AllocationCandidateGroupRecord | None:
        groups = await self.get_groups_for_invoice(
            invoice_id,
        )

        for group in groups:
            if group.is_selected:
                return group

        return None

    async def get_validation_allocations_for_invoice(
        self,
        invoice_id: UUID,
    ) -> list[AllocationRecord]:
        groups = await self.get_groups_for_invoice(
            invoice_id,
        )

        if len(groups) != 1:
            return []

        group = groups[0]

        if group.candidate_type not in _RESERVATION_CANDIDATE_TYPES:
            return []

        if not group.items:
            return []

        po_line_ids = [
            item.po_line_item_id
            for item in group.items
        ]
        stmt = select(
            POLineItem.id,
            POLineItem.po_id,
        ).where(
            POLineItem.id.in_(
                po_line_ids,
            ),
        )
        result = await self.execute(
            stmt,
        )
        po_id_by_line = {
            row.id: row.po_id
            for row in result.all()
        }

        return [
            AllocationRecord(
                invoice_line_item_id=item.invoice_line_item_id,
                po_id=po_id_by_line[item.po_line_item_id],
                po_line_item_id=item.po_line_item_id,
                allocated_quantity=item.allocated_quantity,
                allocated_amount=item.allocated_amount,
            )
            for item in group.items
            if item.po_line_item_id in po_id_by_line
        ]
