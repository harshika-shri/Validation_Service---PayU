from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class InvoiceBusinessContent:
    po_ids: frozenset[UUID]
    allocations: frozenset[tuple[UUID, UUID, Decimal]]
    line_items: frozenset[tuple[str, str, Decimal, Decimal]]
    total_amount: Decimal | None


def build_line_item_fingerprint(
    item_code: str | None,
    item_description: str | None,
    quantity_billed: Decimal,
    unit_price: Decimal,
) -> tuple[str, str, Decimal, Decimal]:
    return (
        (item_code or "").strip().casefold(),
        (item_description or "").strip().casefold(),
        quantity_billed.quantize(
            Decimal("0.001"),
        ),
        unit_price.quantize(
            Decimal("0.01"),
        ),
    )


def business_content_is_identical(
    left: InvoiceBusinessContent,
    right: InvoiceBusinessContent,
) -> bool:
    return left == right
