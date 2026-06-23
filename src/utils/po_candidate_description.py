from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Any
from uuid import UUID

from src.control.agents.po_resolution.line_allocation_search import (
    AllocationRecord,
)
from src.data.repositories.po_resolution.po_line_item_repository import (
    POLineItemRecord,
)
from src.data.repositories.po_resolution.purchase_order_repository import (
    PurchaseOrderRecord,
)

PO_CANDIDATE_CONTEXT_ISSUE_CODES = frozenset(
    {
        "PO_MISSING",
        "PO_RECOVERED",
        "PO_CLOSED",
        "PO_UNRESOLVED",
        "PO_AMBIGUOUS",
        "PO_VENDOR_CONFLICT",
        "PO_RESOLUTION_BLOCKED",
        "INVALID_PO_REFERENCE",
        "MISSING_PO_COVERAGE",
        "UNMATCHED_LINE_ITEM",
        "AMBIGUOUS_LINE_MATCH",
        "QUANTITY_EXCEEDS_ORDERED",
        "QUANTITY_EXCEEDS_REMAINING",
        "INVALID_ALLOCATION",
        "LINE_ITEM_VENDOR_CONFLICT",
    },
)


def group_po_lines_by_po_id(
    po_lines: list[POLineItemRecord],
) -> dict[UUID, list[POLineItemRecord]]:
    grouped: dict[UUID, list[POLineItemRecord]] = {}

    for po_line in po_lines:
        grouped.setdefault(
            po_line.po_id,
            [],
        ).append(
            po_line,
        )

    return grouped


def format_po_line_item(
    po_line: POLineItemRecord,
    *,
    available_quantity: Decimal | None = None,
) -> str:
    item_code = po_line.item_code or "N/A"
    quantity_text = (
        f"ordered {po_line.quantity_ordered}, "
        f"unit price {po_line.unit_price}"
    )

    if available_quantity is not None:
        quantity_text = (
            f"{quantity_text}, available {available_quantity}"
        )

    return (
        f"  - {po_line.item_description} "
        f"(HSN/SAC: {item_code}, {quantity_text})"
    )


def format_candidate_purchase_orders(
    purchase_orders: list[PurchaseOrderRecord],
    po_lines_by_po_id: dict[UUID, list[POLineItemRecord]],
    *,
    available_quantity_by_line_id: dict[UUID, Decimal] | None = None,
) -> str:
    if not purchase_orders:
        return "Candidate purchase orders checked: none."

    lines = [
        "Candidate purchase orders checked:",
    ]

    for purchase_order in sorted(
        purchase_orders,
        key=lambda record: record.po_number,
    ):
        lines.append(
            (
                f"- {purchase_order.po_number} "
                f"(status: {purchase_order.status.value}, "
                f"date: {purchase_order.po_date})"
            ),
        )

        po_lines = po_lines_by_po_id.get(
            purchase_order.id,
            [],
        )

        if not po_lines:
            lines.append(
                "  - (no line items found)",
            )
            continue

        for po_line in po_lines:
            available_quantity = None

            if available_quantity_by_line_id is not None:
                available_quantity = available_quantity_by_line_id.get(
                    po_line.id,
                )

            lines.append(
                format_po_line_item(
                    po_line,
                    available_quantity=available_quantity,
                ),
            )

    return "\n".join(
        lines,
    )


def format_po_set_options(
    solutions: set[frozenset[UUID]],
    po_by_id: dict[UUID, PurchaseOrderRecord],
) -> str:
    if not solutions:
        return ""

    lines = [
        "Valid PO combinations found:",
    ]

    for index, solution in enumerate(
        sorted(
            solutions,
            key=lambda po_set: tuple(
                sorted(
                    str(po_id)
                    for po_id in po_set
                ),
            ),
        ),
        start=1,
    ):
        po_numbers = ", ".join(
            sorted(
                po_by_id[po_id].po_number
                for po_id in solution
                if po_id in po_by_id
            ),
        )
        lines.append(
            f"  {index}. {po_numbers or 'unknown'}",
        )

    return "\n".join(
        lines,
    )


def format_allocation_plan_options(
    allocation_plans: set[tuple[AllocationRecord, ...]],
    po_by_id: dict[UUID, PurchaseOrderRecord],
    po_line_by_id: dict[UUID, POLineItemRecord],
) -> str:
    if not allocation_plans:
        return ""

    lines = [
        "Valid line allocation plans found:",
    ]

    for index, plan in enumerate(
        sorted(
            allocation_plans,
            key=lambda allocations: tuple(
                (
                    str(record.invoice_line_item_id),
                    str(record.po_line_item_id),
                    str(record.allocated_quantity),
                )
                for record in allocations
            ),
        ),
        start=1,
    ):
        allocation_parts: list[str] = []

        for record in plan:
            po_number = po_by_id.get(
                record.po_id,
            )
            po_line = po_line_by_id.get(
                record.po_line_item_id,
            )
            po_label = (
                po_number.po_number
                if po_number is not None
                else str(record.po_id)
            )
            line_label = (
                po_line.item_description
                if po_line is not None
                else "line item"
            )
            allocation_parts.append(
                (
                    f"{line_label} -> {po_label} "
                    f"(qty {record.allocated_quantity})"
                ),
            )

        lines.append(
            f"  {index}. {'; '.join(allocation_parts)}",
        )

    return "\n".join(
        lines,
    )


def append_po_context(
    base_description: str,
    context: str,
) -> str:
    context = context.strip()

    if not context:
        return base_description

    return (
        f"{base_description.rstrip()}\n\n{context}"
    )


def build_po_issue_context(
    *,
    purchase_orders: list[PurchaseOrderRecord],
    po_lines: list[POLineItemRecord],
    available_quantity_by_line_id: dict[UUID, Decimal] | None = None,
    po_set_solutions: set[frozenset[UUID]] | None = None,
    allocation_plans: set[tuple[AllocationRecord, ...]] | None = None,
) -> str:
    po_by_id = {
        purchase_order.id: purchase_order
        for purchase_order in purchase_orders
    }
    po_lines_by_po_id = group_po_lines_by_po_id(
        po_lines,
    )
    sections = [
        format_candidate_purchase_orders(
            purchase_orders,
            po_lines_by_po_id,
            available_quantity_by_line_id=(
                available_quantity_by_line_id
            ),
        ),
    ]

    if po_set_solutions:
        po_set_text = format_po_set_options(
            po_set_solutions,
            po_by_id,
        )

        if po_set_text:
            sections.append(
                po_set_text,
            )

    if allocation_plans:
        po_line_by_id = {
            po_line.id: po_line
            for po_line in po_lines
        }
        plan_text = format_allocation_plan_options(
            allocation_plans,
            po_by_id,
            po_line_by_id,
        )

        if plan_text:
            sections.append(
                plan_text,
            )

    return "\n\n".join(
        section
        for section in sections
        if section.strip()
    )


def build_candidate_pos_metadata(
    *,
    purchase_orders: list[PurchaseOrderRecord],
    po_lines: list[POLineItemRecord],
    available_quantity_by_line_id: dict[UUID, Decimal] | None = None,
    po_set_solutions: set[frozenset[UUID]] | None = None,
    resolved_po_ids: frozenset[UUID] | None = None,
) -> dict[str, Any]:
    po_by_id = {
        purchase_order.id: purchase_order
        for purchase_order in purchase_orders
    }
    po_lines_by_po_id = group_po_lines_by_po_id(
        po_lines,
    )
    candidate_pos: list[dict[str, Any]] = []

    for purchase_order in sorted(
        purchase_orders,
        key=lambda record: record.po_number,
    ):
        matching_items: list[str] = []
        available_quantities: dict[str, str] = {}

        for po_line in po_lines_by_po_id.get(
            purchase_order.id,
            [],
        ):
            matching_items.append(
                po_line.item_description,
            )
            available_value = po_line.quantity_ordered

            if available_quantity_by_line_id is not None:
                available_value = available_quantity_by_line_id.get(
                    po_line.id,
                    Decimal(0),
                )

            available_quantities[
                po_line.item_description
            ] = str(
                available_value,
            )

        candidate_pos.append(
            {
                "po_number": purchase_order.po_number,
                "po_id": str(
                    purchase_order.id,
                ),
                "matching_items": matching_items,
                "available_quantities": available_quantities,
            },
        )

    metadata: dict[str, Any] = {
        "candidate_pos": candidate_pos,
    }

    if po_set_solutions:
        metadata["valid_solutions"] = [
            [
                po_by_id[po_id].po_number
                for po_id in sorted(
                    solution,
                    key=str,
                )
                if po_id in po_by_id
            ]
            for solution in sorted(
                po_set_solutions,
                key=lambda po_set: tuple(
                    sorted(
                        str(po_id)
                        for po_id in po_set
                    ),
                ),
            )
        ]

    if resolved_po_ids:
        metadata["resolved_po_numbers"] = [
            po_by_id[po_id].po_number
            for po_id in sorted(
                resolved_po_ids,
                key=str,
            )
            if po_id in po_by_id
        ]

    return metadata


def enrich_pending_issues_with_po_context(
    pending_issues: list[Any],
    context: str,
    *,
    issue_codes: frozenset[str] = PO_CANDIDATE_CONTEXT_ISSUE_CODES,
    issue_metadata: dict[str, Any] | None = None,
) -> list[Any]:
    if not context.strip() and not issue_metadata:
        return pending_issues

    enriched: list[Any] = []

    for pending_issue in pending_issues:
        if pending_issue.issue_code not in issue_codes:
            enriched.append(
                pending_issue,
            )
            continue

        updated = pending_issue

        if context.strip():
            updated = replace(
                updated,
                description=append_po_context(
                    updated.description,
                    context,
                ),
            )

        if issue_metadata:
            merged_metadata = dict(
                updated.metadata or {},
            )
            merged_metadata.update(
                issue_metadata,
            )
            updated = replace(
                updated,
                metadata=merged_metadata,
            )

        enriched.append(
            updated,
        )

    return enriched
