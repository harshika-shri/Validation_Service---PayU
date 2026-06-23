from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from src.data.models.postgres.invoice_line_items import InvoiceLineItem
from src.data.repositories.base_repo import BaseRepository


@dataclass(frozen=True, slots=True)
class InvoiceLineAmountRecord:
    id: UUID
    quantity_billed: Decimal
    unit_price: Decimal
    discount_amount: Decimal | None
    tax_details: dict | None
    line_total: Decimal


class InvoiceLineAmountRepository(BaseRepository):
    async def get_by_invoice_id(
        self,
        invoice_id: UUID,
    ) -> list[InvoiceLineAmountRecord]:
        stmt = (
            select(
                InvoiceLineItem.id,
                InvoiceLineItem.quantity_billed,
                InvoiceLineItem.unit_price,
                InvoiceLineItem.discount_amount,
                InvoiceLineItem.tax_details,
                InvoiceLineItem.line_total,
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
            InvoiceLineAmountRecord(
                id=row.id,
                quantity_billed=row.quantity_billed,
                unit_price=row.unit_price,
                discount_amount=row.discount_amount,
                tax_details=row.tax_details,
                line_total=row.line_total,
            )
            for row in result.all()
        ]
