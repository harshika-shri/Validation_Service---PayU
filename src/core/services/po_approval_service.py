from __future__ import annotations

from uuid import UUID

from src.core.services.allocation_lifecycle_service import (
    AllocationLifecycleService,
)
from src.data.models.postgres.enums import AllocationMatchType
from src.data.repositories.po_resolution.invoice_line_allocation_candidate_repository import (
    InvoiceLineAllocationCandidateRepository,
)
from src.data.repositories.po_resolution.invoice_line_po_allocation_repository import (
    AllocationCreate,
    InvoiceLinePOAllocationRepository,
)
from src.data.repositories.po_resolution.invoice_po_mapping_repository import (
    InvoicePOMappingRepository,
)
from src.data.repositories.po_resolution.invoice_po_resolution_group_repository import (
    InvoicePOResolutionGroupRepository,
)
from src.data.repositories.po_resolution.po_line_item_repository import (
    POLineItemRepository,
)


class PoApprovalService:
    def __init__(
        self,
        resolution_group_repo: InvoicePOResolutionGroupRepository,
        allocation_candidate_repo: InvoiceLineAllocationCandidateRepository,
        invoice_po_mapping_repo: InvoicePOMappingRepository,
        allocation_repo: InvoiceLinePOAllocationRepository,
        po_line_item_repo: POLineItemRepository,
        allocation_lifecycle_service: AllocationLifecycleService,
    ) -> None:
        self._resolution_group_repo = resolution_group_repo
        self._allocation_candidate_repo = allocation_candidate_repo
        self._invoice_po_mapping_repo = invoice_po_mapping_repo
        self._allocation_repo = allocation_repo
        self._po_line_item_repo = po_line_item_repo
        self._allocation_lifecycle_service = allocation_lifecycle_service

    async def finalize_selected_resolution_group(
        self,
        invoice_id: UUID,
        group_id: UUID,
    ) -> list[UUID]:
        selected_group = await self._resolution_group_repo.select_group(
            invoice_id=invoice_id,
            group_id=group_id,
        )

        if selected_group is None:
            msg = (
                f"Resolution group {group_id} was not found for "
                f"invoice {invoice_id}."
            )
            raise ValueError(
                msg,
            )

        await self._invoice_po_mapping_repo.delete_mappings_for_invoice(
            invoice_id,
        )
        await self._invoice_po_mapping_repo.create_mappings(
            invoice_id=invoice_id,
            po_ids=sorted(
                selected_group.po_ids,
                key=str,
            ),
        )

        return selected_group.po_ids

    async def finalize_selected_allocation_group(
        self,
        invoice_id: UUID,
        group_id: UUID,
    ) -> int:
        selected_group = await self._allocation_candidate_repo.select_group(
            invoice_id=invoice_id,
            group_id=group_id,
        )

        if selected_group is None:
            msg = (
                f"Allocation candidate group {group_id} was not found "
                f"for invoice {invoice_id}."
            )
            raise ValueError(
                msg,
            )

        po_line_ids = [
            item.po_line_item_id
            for item in selected_group.items
        ]
        po_lines = await self._po_line_item_repo.get_by_ids(
            po_line_ids,
        )
        po_id_by_line = {
            po_line.id: po_line.po_id
            for po_line in po_lines
        }

        allocations = [
            AllocationCreate(
                invoice_line_item_id=item.invoice_line_item_id,
                po_id=po_id_by_line[item.po_line_item_id],
                po_line_item_id=item.po_line_item_id,
                allocated_quantity=item.allocated_quantity,
                allocated_amount=item.allocated_amount,
                match_type=AllocationMatchType.EXACT,
            )
            for item in selected_group.items
            if item.po_line_item_id in po_id_by_line
        ]

        await self._allocation_repo.replace_pending_allocations_for_invoice(
            invoice_id=invoice_id,
            allocations=allocations,
        )

        return len(
            allocations,
        )

    async def commit_invoice_allocations(
        self,
        invoice_id: UUID,
    ) -> int:
        po_line_ids = (
            await self._allocation_lifecycle_service.commit_allocations(
                invoice_id,
            )
        )

        return len(
            po_line_ids,
        )
