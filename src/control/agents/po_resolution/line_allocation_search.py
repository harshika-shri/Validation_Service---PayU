from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from src.data.models.postgres.enums import AllocationMatchType


@dataclass(frozen=True, slots=True)
class AllocationRecord:
    invoice_line_item_id: UUID
    po_id: UUID
    po_line_item_id: UUID
    allocated_quantity: Decimal
    match_type: AllocationMatchType


@dataclass(frozen=True, slots=True)
class LineMatchEdge:
    po_line_id: UUID
    match_type: AllocationMatchType


def canonicalize_plan(
    allocations: tuple[AllocationRecord, ...],
) -> tuple[AllocationRecord, ...]:
    return tuple(
        sorted(
            allocations,
            key=lambda record: (
                str(record.invoice_line_item_id),
                str(record.po_line_item_id),
                record.allocated_quantity,
            ),
        ),
    )


def find_all_allocation_plans(
    invoice_line_ids: list[UUID],
    quantity_by_line: dict[UUID, Decimal],
    match_edges: dict[UUID, list[LineMatchEdge]],
    po_line_capacity: dict[UUID, Decimal],
    po_line_to_po: dict[UUID, UUID],
) -> set[tuple[AllocationRecord, ...]]:
    solutions: set[tuple[AllocationRecord, ...]] = set()

    if not invoice_line_ids:
        return solutions

    def dfs(
        line_idx: int,
        consumed: dict[UUID, Decimal],
        prior_allocations: list[AllocationRecord],
    ) -> None:
        if line_idx >= len(
            invoice_line_ids,
        ):
            plan = canonicalize_plan(
                tuple(
                    prior_allocations,
                ),
            )
            solutions.add(
                plan,
            )
            return

        invoice_line_id = invoice_line_ids[
            line_idx
        ]
        needed = quantity_by_line[
            invoice_line_id
        ]
        matching_edges = match_edges.get(
            invoice_line_id,
            [],
        )

        if not matching_edges:
            return

        def backtrack(
            remaining: Decimal,
            edge_idx: int,
            consumed_copy: dict[UUID, Decimal],
            line_allocations: list[AllocationRecord],
        ) -> None:
            if remaining <= 0:
                finalized = _finalize_line_allocations(
                    invoice_line_id=invoice_line_id,
                    line_allocations=line_allocations,
                    po_line_to_po=po_line_to_po,
                )
                dfs(
                    line_idx + 1,
                    consumed_copy,
                    [
                        *prior_allocations,
                        *finalized,
                    ],
                )
                return

            if edge_idx >= len(
                matching_edges,
            ):
                return

            edge = matching_edges[
                edge_idx
            ]
            po_line_id = edge.po_line_id
            used_on_line = consumed_copy.get(
                po_line_id,
                Decimal(0),
            )
            available = po_line_capacity[
                po_line_id
            ] - used_on_line

            backtrack(
                remaining,
                edge_idx + 1,
                consumed_copy,
                line_allocations,
            )

            if available > 0:
                max_take = min(
                    available,
                    remaining,
                )
                take = Decimal(1)

                while take <= max_take:
                    consumed_copy[
                        po_line_id
                    ] = used_on_line + take
                    allocation = AllocationRecord(
                        invoice_line_item_id=invoice_line_id,
                        po_id=po_line_to_po[
                            po_line_id
                        ],
                        po_line_item_id=po_line_id,
                        allocated_quantity=take,
                        match_type=edge.match_type,
                    )
                    backtrack(
                        remaining - take,
                        edge_idx + 1,
                        consumed_copy,
                        [
                            *line_allocations,
                            allocation,
                        ],
                    )
                    take += Decimal(1)

                if used_on_line == 0:
                    consumed_copy.pop(
                        po_line_id,
                        None,
                    )
                else:
                    consumed_copy[
                        po_line_id
                    ] = used_on_line

        backtrack(
            needed,
            0,
            dict(
                consumed,
            ),
            [],
        )

    dfs(
        0,
        {},
        [],
    )

    return solutions


def _finalize_line_allocations(
    invoice_line_id: UUID,
    line_allocations: list[AllocationRecord],
    po_line_to_po: dict[UUID, UUID],
) -> list[AllocationRecord]:
    if len(line_allocations) <= 1:
        return line_allocations

    return [
        AllocationRecord(
            invoice_line_item_id=invoice_line_id,
            po_id=po_line_to_po[
                allocation.po_line_item_id
            ],
            po_line_item_id=allocation.po_line_item_id,
            allocated_quantity=allocation.allocated_quantity,
            match_type=AllocationMatchType.SPLIT,
        )
        for allocation in line_allocations
    ]
