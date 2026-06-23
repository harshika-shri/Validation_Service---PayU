from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from src.data.models.postgres.invoice_line_items import InvoiceLineItem
from src.data.repositories.base_repo import BaseRepository


@dataclass(frozen=True, slots=True)
class InvoiceLineItemRecord:
    id: UUID
    line_number: int
    item_code: str | None
    item_description: str | None
    hsn_sac_code: str | None
    quantity_billed: Decimal
    unit_price: Decimal


class InvoiceLineItemRepository(BaseRepository):
    async def get_by_invoice_id(
        self,
        invoice_id: UUID,
    ) -> list[InvoiceLineItemRecord]:
        stmt = (
            select(
                InvoiceLineItem.id,
                InvoiceLineItem.line_number,
                InvoiceLineItem.item_code,
                InvoiceLineItem.item_description,
                InvoiceLineItem.hsn_sac_code,
                InvoiceLineItem.quantity_billed,
                InvoiceLineItem.unit_price,
            )
            .where(
                InvoiceLineItem.invoice_id == invoice_id,
            )
            .order_by(
                InvoiceLineItem.line_number,
            )
        )

        result = await self.execute(
            stmt,
        )

        return [
            InvoiceLineItemRecord(
                id=row.id,
                line_number=row.line_number,
                item_code=row.item_code,
                item_description=row.item_description,
                hsn_sac_code=row.hsn_sac_code,
                quantity_billed=row.quantity_billed,
                unit_price=row.unit_price,
            )
            for row in result.all()
        ]
