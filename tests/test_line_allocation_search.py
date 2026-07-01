from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from src.control.agents.po_resolution.line_allocation_search import (
    AllocationRecord,
    LineMatchEdge,
    find_all_allocation_plans,
)
from src.data.models.postgres.enums import AllocationMatchType


def _line_id() -> object:
    return uuid4()


def _po_line_id() -> object:
    return uuid4()


def test_find_all_allocation_plans_finds_multiple_splits() -> None:
    invoice_line_id = _line_id()
    po1_line_id = _po_line_id()
    po2_line_id = _po_line_id()
    po1_id = uuid4()
    po2_id = uuid4()

    plans = find_all_allocation_plans(
        invoice_line_ids=[invoice_line_id],
        quantity_by_line={
            invoice_line_id: Decimal(4),
        },
        match_edges={
            invoice_line_id: [
                LineMatchEdge(
                    po_line_id=po1_line_id,
                    match_type=AllocationMatchType.EXACT_CODE,
                ),
                LineMatchEdge(
                    po_line_id=po2_line_id,
                    match_type=AllocationMatchType.EXACT_CODE,
                ),
            ],
        },
        po_line_capacity={
            po1_line_id: Decimal(2),
            po2_line_id: Decimal(3),
        },
        po_line_to_po={
            po1_line_id: po1_id,
            po2_line_id: po2_id,
        },
    )

    assert len(plans) == 2

    plan_signatures = {
        tuple(
            sorted(
                (
                    record.po_line_item_id,
                    record.allocated_quantity,
                )
                for record in plan
            ),
        )
        for plan in plans
    }

    assert plan_signatures == {
        (
            (po1_line_id, Decimal(1)),
            (po2_line_id, Decimal(3)),
        ),
        (
            (po1_line_id, Decimal(2)),
            (po2_line_id, Decimal(2)),
        ),
    }


def test_find_all_allocation_plans_single_plan_when_unique() -> None:
    invoice_line_id = _line_id()
    po_line_id = _po_line_id()
    po_id = uuid4()

    plans = find_all_allocation_plans(
        invoice_line_ids=[invoice_line_id],
        quantity_by_line={
            invoice_line_id: Decimal(2),
        },
        match_edges={
            invoice_line_id: [
                LineMatchEdge(
                    po_line_id=po_line_id,
                    match_type=AllocationMatchType.EXACT_CODE,
                ),
            ],
        },
        po_line_capacity={
            po_line_id: Decimal(2),
        },
        po_line_to_po={
            po_line_id: po_id,
        },
    )

    assert len(plans) == 1
    plan = next(iter(plans))
    assert plan == (
        AllocationRecord(
            invoice_line_item_id=invoice_line_id,
            po_id=po_id,
            po_line_item_id=po_line_id,
            allocated_quantity=Decimal(2),
            match_type=AllocationMatchType.EXACT_CODE,
        ),
    )
