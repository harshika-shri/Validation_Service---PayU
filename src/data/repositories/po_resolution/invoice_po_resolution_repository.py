from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import select

from src.data.models.postgres.invoices import Invoice
from src.data.repositories.base_repo import BaseRepository
from src.utils.po_number_utils import (
    parse_po_numbers,
)


@dataclass(frozen=True, slots=True)
class POResolutionInvoiceRecord:
    id: UUID
    invoice_date: date | None
    po_numbers_extracted: list[str]


class InvoicePOResolutionRepository(BaseRepository):
    async def get_po_resolution_invoice(
        self,
        invoice_id: UUID,
    ) -> POResolutionInvoiceRecord | None:
        stmt = select(
            Invoice.id,
            Invoice.invoice_date,
            Invoice.po_numbers_extracted,
        ).where(
            Invoice.id == invoice_id,
        )

        result = await self.execute(
            stmt,
        )
        row = result.one_or_none()

        if row is None:
            return None

        extracted_numbers = parse_po_numbers(
            row.po_numbers_extracted,
        )

        return POResolutionInvoiceRecord(
            id=row.id,
            invoice_date=row.invoice_date,
            po_numbers_extracted=extracted_numbers,
        )

