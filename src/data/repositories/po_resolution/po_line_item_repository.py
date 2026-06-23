from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from src.data.models.postgres.po_line_items import POLineItem
from src.data.repositories.base_repo import BaseRepository


@dataclass(frozen=True, slots=True)
class POLineItemRecord:
    id: UUID
    po_id: UUID
    item_code: str | None
    item_description: str
    quantity_ordered: Decimal
    consumed_quantity: Decimal
    unit_price: Decimal
    discount_amount: Decimal | None
    tax_details: dict | None
    line_total: Decimal


class POLineItemRepository(BaseRepository):
    async def get_by_po_ids(
        self,
        po_ids: list[UUID],
    ) -> list[POLineItemRecord]:
        if not po_ids:
            return []

        stmt = (
            select(
                POLineItem.id,
                POLineItem.po_id,
                POLineItem.item_code,
                POLineItem.item_description,
                POLineItem.quantity_ordered,
                POLineItem.consumed_quantity,
                POLineItem.unit_price,
                POLineItem.discount_amount,
                POLineItem.tax_details,
                POLineItem.line_total,
            )
            .where(
                POLineItem.po_id.in_(
                    po_ids,
                ),
            )
            .order_by(
                POLineItem.po_id,
                POLineItem.line_number,
            )
        )

        result = await self.execute(
            stmt,
        )

        return [
            POLineItemRecord(
                id=row.id,
                po_id=row.po_id,
                item_code=row.item_code,
                item_description=row.item_description,
                quantity_ordered=row.quantity_ordered,
                consumed_quantity=row.consumed_quantity,
                unit_price=row.unit_price,
                discount_amount=row.discount_amount,
                tax_details=row.tax_details,
                line_total=row.line_total,
            )
            for row in result.all()
        ]

    async def get_by_ids(
        self,
        po_line_item_ids: list[UUID],
    ) -> list[POLineItemRecord]:
        if not po_line_item_ids:
            return []

        stmt = (
            select(
                POLineItem.id,
                POLineItem.po_id,
                POLineItem.item_code,
                POLineItem.item_description,
                POLineItem.quantity_ordered,
                POLineItem.consumed_quantity,
                POLineItem.unit_price,
                POLineItem.discount_amount,
                POLineItem.tax_details,
                POLineItem.line_total,
            )
            .where(
                POLineItem.id.in_(
                    po_line_item_ids,
                ),
            )
        )

        result = await self.execute(
            stmt,
        )

        return [
            POLineItemRecord(
                id=row.id,
                po_id=row.po_id,
                item_code=row.item_code,
                item_description=row.item_description,
                quantity_ordered=row.quantity_ordered,
                consumed_quantity=row.consumed_quantity,
                unit_price=row.unit_price,
                discount_amount=row.discount_amount,
                tax_details=row.tax_details,
                line_total=row.line_total,
            )
            for row in result.all()
        ]
