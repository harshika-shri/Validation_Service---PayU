from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID


def filter_pos_by_invoice_date(
    po_dates: dict[UUID, date],
    invoice_date: date | None,
    *,
    window_days: int,
) -> set[UUID]:
    if invoice_date is None:
        return set(
            po_dates.keys(),
        )

    window = timedelta(
        days=window_days,
    )
    eligible: set[UUID] = set()

    for po_id, po_date in po_dates.items():
        if abs(
            (invoice_date - po_date).days,
        ) <= window.days:
            eligible.add(
                po_id,
            )

    return eligible


def find_all_valid_po_sets(
    invoice_line_ids: list[UUID],
    quantity_by_line: dict[UUID, Decimal],
    match_edges: dict[UUID, list[UUID]],
    po_line_capacity: dict[UUID, Decimal],
    po_line_to_po: dict[UUID, UUID],
) -> set[frozenset[UUID]]:
    solutions: set[frozenset[UUID]] = set()

    if not invoice_line_ids:
        return solutions

    def dfs(
        line_idx: int,
        consumed: dict[UUID, Decimal],
    ) -> None:
        if line_idx >= len(
            invoice_line_ids,
        ):
            used_po_ids = frozenset(
                po_line_to_po[po_line_id]
                for po_line_id, qty in consumed.items()
                if qty > 0
            )

            if used_po_ids:
                solutions.add(
                    used_po_ids,
                )

            return

        invoice_line_id = invoice_line_ids[
            line_idx
        ]
        needed = quantity_by_line[
            invoice_line_id
        ]
        matching_po_lines = match_edges.get(
            invoice_line_id,
            [],
        )

        if not matching_po_lines:
            return

        def backtrack(
            remaining: Decimal,
            po_line_idx: int,
            consumed_copy: dict[UUID, Decimal],
        ) -> None:
            if remaining <= 0:
                dfs(
                    line_idx + 1,
                    consumed_copy,
                )
                return

            if po_line_idx >= len(
                matching_po_lines,
            ):
                return

            po_line_id = matching_po_lines[
                po_line_idx
            ]
            used_on_line = consumed_copy.get(
                po_line_id,
                Decimal(0),
            )
            available = po_line_capacity[
                po_line_id
            ] - used_on_line

            backtrack(
                remaining,
                po_line_idx + 1,
                consumed_copy,
            )

            if available > 0:
                take = min(
                    available,
                    remaining,
                )
                consumed_copy[
                    po_line_id
                ] = used_on_line + take
                backtrack(
                    remaining - take,
                    po_line_idx,
                    consumed_copy,
                )
                backtrack(
                    remaining - take,
                    po_line_idx + 1,
                    consumed_copy,
                )

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
        )

    dfs(
        0,
        {},
    )

    return solutions
