from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from src.data.models.postgres.invoices import Invoice
from src.data.repositories.base_repo import BaseRepository


@dataclass(frozen=True, slots=True)
class InvoiceAmountRecord:
    id: UUID
    subtotal_amount: Decimal | None
    tax_amount: Decimal | None
    total_amount: Decimal | None
    discount_amount: Decimal | None
    notes: str | None


class InvoiceAmountRepository(BaseRepository):
    async def get_by_invoice_id(
        self,
        invoice_id: UUID,
    ) -> InvoiceAmountRecord | None:
        stmt = select(
            Invoice.id,
            Invoice.subtotal_amount,
            Invoice.tax_amount,
            Invoice.total_amount,
            Invoice.discount_amount,
            Invoice.notes,
        ).where(
            Invoice.id == invoice_id,
        )

        result = await self.execute(
            stmt,
        )
        row = result.one_or_none()

        if row is None:
            return None

        return InvoiceAmountRecord(
            id=row.id,
            subtotal_amount=row.subtotal_amount,
            tax_amount=row.tax_amount,
            total_amount=row.total_amount,
            discount_amount=row.discount_amount,
            notes=row.notes,
        )
