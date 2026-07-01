from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from uuid import UUID

from src.control.agents.po_resolution.line_allocation_search import (
    AllocationRecord,
    LineMatchEdge,
    find_all_allocation_plans,
)
from src.control.agents.po_resolution.po_line_matcher import (
    POLineMatcher,
)
from src.data.models.postgres.enums import PurchaseOrderStatus
from src.data.repositories.line_item_validation.invoice_line_item_repository import (
    InvoiceLineItemRecord,
)
from src.data.repositories.po_resolution.po_line_item_repository import (
    POLineItemRecord,
)
from src.data.repositories.po_resolution.po_line_quantity_repository import (
    POLineQuantityRepository,
)
from src.data.repositories.po_resolution.purchase_order_repository import (
    PurchaseOrderRecord,
    PurchaseOrderRepository,
)


class AllocationWorkflowStatus(str, Enum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    NEEDS_ADDITIONAL_POS = "needs_additional_pos"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class AllocationWorkflowState:
    status: AllocationWorkflowStatus
    po_ids: list[UUID]
    po_lines: list[POLineItemRecord]
    purchase_orders: list[PurchaseOrderRecord]
    match_edges: dict[UUID, list[LineMatchEdge]]
    po_line_capacity: dict[UUID, Decimal]
    po_line_to_po: dict[UUID, UUID]
    po_line_by_id: dict[UUID, POLineItemRecord]
    allocation_plans: set[tuple[AllocationRecord, ...]]
    uncovered_line_ids: tuple[UUID, ...]
    insufficient_quantity_line_ids: tuple[UUID, ...]
    expanded_candidate_set: bool = False


_ACTIVE_PO_STATUSES = (
    PurchaseOrderStatus.OPEN,
    PurchaseOrderStatus.PARTIALLY_PROCESSED,
)


async def evaluate_allocation_workflow(
    *,
    invoice_id: UUID,
    invoice_lines: list[InvoiceLineItemRecord],
    candidate_po_ids: list[UUID],
    po_line_item_repo,
    po_line_quantity_repo: POLineQuantityRepository,
    purchase_order_repo: PurchaseOrderRepository,
    matcher: POLineMatcher,
) -> AllocationWorkflowState:
    po_lines = await po_line_item_repo.get_by_po_ids(
        candidate_po_ids,
    )
    purchase_orders = await purchase_order_repo.get_by_ids(
        candidate_po_ids,
    )

    match_edges = await matcher.build_typed_match_edges(
        invoice_lines=invoice_lines,
        po_lines=po_lines,
    )

    quantity_ordered_by_id = {
        po_line.id: po_line.quantity_ordered
        for po_line in po_lines
    }
    po_line_capacity = await po_line_quantity_repo.get_available_quantities(
        po_line_ids=[
            po_line.id
            for po_line in po_lines
        ],
        quantity_ordered_by_id=quantity_ordered_by_id,
        exclude_invoice_id=invoice_id,
    )
    po_line_to_po = {
        po_line.id: po_line.po_id
        for po_line in po_lines
    }
    po_line_by_id = {
        po_line.id: po_line
        for po_line in po_lines
    }

    allocation_plans = find_all_allocation_plans(
        invoice_line_ids=[
            line.id
            for line in invoice_lines
        ],
        quantity_by_line={
            line.id: line.quantity_billed
            for line in invoice_lines
        },
        match_edges=match_edges,
        po_line_capacity=po_line_capacity,
        po_line_to_po=po_line_to_po,
    )

    uncovered_line_ids = tuple(
        line.id
        for line in invoice_lines
        if not match_edges.get(
            line.id,
            [],
        )
    )
    insufficient_quantity_line_ids = tuple(
        _lines_with_insufficient_capacity(
            invoice_lines=invoice_lines,
            match_edges=match_edges,
            po_line_capacity=po_line_capacity,
        )
    )

    status = _classify_allocation_status(
        allocation_plans=allocation_plans,
        uncovered_line_ids=uncovered_line_ids,
        insufficient_quantity_line_ids=insufficient_quantity_line_ids,
        invoice_lines=invoice_lines,
        match_edges=match_edges,
        po_line_capacity=po_line_capacity,
    )

    return AllocationWorkflowState(
        status=status,
        po_ids=list(
            candidate_po_ids,
        ),
        po_lines=po_lines,
        purchase_orders=purchase_orders,
        match_edges=match_edges,
        po_line_capacity=po_line_capacity,
        po_line_to_po=po_line_to_po,
        po_line_by_id=po_line_by_id,
        allocation_plans=allocation_plans,
        uncovered_line_ids=uncovered_line_ids,
        insufficient_quantity_line_ids=insufficient_quantity_line_ids,
    )


def _classify_allocation_status(
    *,
    allocation_plans: set[tuple[AllocationRecord, ...]],
    uncovered_line_ids: tuple[UUID, ...],
    insufficient_quantity_line_ids: tuple[UUID, ...],
    invoice_lines: list[InvoiceLineItemRecord],
    match_edges: dict[UUID, list[LineMatchEdge]],
    po_line_capacity: dict[UUID, Decimal],
) -> AllocationWorkflowStatus:
    if len(
        allocation_plans,
    ) > 1:
        return AllocationWorkflowStatus.AMBIGUOUS

    if len(
        allocation_plans,
    ) == 1:
        return AllocationWorkflowStatus.RESOLVED

    if uncovered_line_ids or insufficient_quantity_line_ids:
        return AllocationWorkflowStatus.NEEDS_ADDITIONAL_POS

    if not invoice_lines:
        return AllocationWorkflowStatus.RESOLVED

    if all(
        match_edges.get(
            line.id,
            [],
        )
        for line in invoice_lines
    ) and _total_available_capacity(
        invoice_lines=invoice_lines,
        match_edges=match_edges,
        po_line_capacity=po_line_capacity,
    ) >= sum(
        (
            line.quantity_billed
            for line in invoice_lines
        ),
        Decimal(0),
    ):
        return AllocationWorkflowStatus.UNRESOLVED

    return AllocationWorkflowStatus.UNRESOLVED


def _lines_with_insufficient_capacity(
    *,
    invoice_lines: list[InvoiceLineItemRecord],
    match_edges: dict[UUID, list[LineMatchEdge]],
    po_line_capacity: dict[UUID, Decimal],
) -> list[UUID]:
    insufficient: list[UUID] = []

    for line in invoice_lines:
        edges = match_edges.get(
            line.id,
            [],
        )

        if not edges:
            continue

        total_available = _available_for_edges(
            edges=edges,
            po_line_capacity=po_line_capacity,
        )

        if total_available < line.quantity_billed:
            insufficient.append(
                line.id,
            )

    return insufficient


def _total_available_capacity(
    *,
    invoice_lines: list[InvoiceLineItemRecord],
    match_edges: dict[UUID, list[LineMatchEdge]],
    po_line_capacity: dict[UUID, Decimal],
) -> Decimal:
    return sum(
        (
            _available_for_edges(
                edges=match_edges.get(
                    line.id,
                    [],
                ),
                po_line_capacity=po_line_capacity,
            )
            for line in invoice_lines
        ),
        Decimal(0),
    )


def _available_for_edges(
    *,
    edges: list[LineMatchEdge],
    po_line_capacity: dict[UUID, Decimal],
) -> Decimal:
    return sum(
        (
            po_line_capacity.get(
                edge.po_line_id,
                Decimal(0),
            )
            for edge in edges
        ),
        Decimal(0),
    )


async def find_additional_po_ids(
    *,
    invoice_id: UUID,
    invoice_lines: list[InvoiceLineItemRecord],
    current_po_ids: set[UUID],
    uncovered_line_ids: tuple[UUID, ...],
    insufficient_quantity_line_ids: tuple[UUID, ...],
    vendor_master_id: UUID | None,
    matcher: POLineMatcher,
    po_line_item_repo,
    po_line_quantity_repo: POLineQuantityRepository,
    purchase_order_repo: PurchaseOrderRepository,
) -> list[UUID]:
    if vendor_master_id is None:
        return []

    if not uncovered_line_ids and not insufficient_quantity_line_ids:
        return []

    target_line_ids = set(
        uncovered_line_ids,
    ) | set(
        insufficient_quantity_line_ids,
    )
    lines_by_id = {
        line.id: line
        for line in invoice_lines
    }
    target_lines = [
        lines_by_id[line_id]
        for line_id in target_line_ids
        if line_id in lines_by_id
    ]

    if not target_lines:
        return []

    vendor_pos = await purchase_order_repo.find_by_vendor_and_statuses(
        vendor_id=vendor_master_id,
        statuses=list(
            _ACTIVE_PO_STATUSES,
        ),
    )

    additional_po_ids: list[UUID] = []

    for purchase_order in vendor_pos:
        if purchase_order.id in current_po_ids:
            continue

        po_lines = await po_line_item_repo.get_by_po_ids(
            [
                purchase_order.id,
            ],
        )

        if not po_lines:
            continue

        match_edges = await matcher.build_typed_match_edges(
            invoice_lines=target_lines,
            po_lines=po_lines,
        )

        quantity_ordered_by_id = {
            po_line.id: po_line.quantity_ordered
            for po_line in po_lines
        }
        po_line_capacity = (
            await po_line_quantity_repo.get_available_quantities(
                po_line_ids=[
                    po_line.id
                    for po_line in po_lines
                ],
                quantity_ordered_by_id=quantity_ordered_by_id,
                exclude_invoice_id=invoice_id,
            )
        )

        if _purchase_order_can_help(
            target_line_ids=target_line_ids,
            match_edges=match_edges,
            po_line_capacity=po_line_capacity,
            lines_by_id=lines_by_id,
        ):
            additional_po_ids.append(
                purchase_order.id,
            )

    return additional_po_ids


def _purchase_order_can_help(
    *,
    target_line_ids: set[UUID],
    match_edges: dict[UUID, list[LineMatchEdge]],
    po_line_capacity: dict[UUID, Decimal],
    lines_by_id: dict[UUID, InvoiceLineItemRecord],
) -> bool:
    for line_id in target_line_ids:
        edges = match_edges.get(
            line_id,
            [],
        )

        if not edges:
            continue

        available = _available_for_edges(
            edges=edges,
            po_line_capacity=po_line_capacity,
        )

        if available <= 0:
            continue

        invoice_line = lines_by_id.get(
            line_id,
        )

        if invoice_line is None:
            continue

        if available > 0:
            return True

    return False
