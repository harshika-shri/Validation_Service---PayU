from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from src.data.models.postgres.invoice_line_items import InvoiceLineItem
from src.data.models.postgres.invoices import Invoice
from src.data.repositories.base_repo import BaseRepository
from src.utils.duplicate_detection_utils import (
    InvoiceBusinessContent,
    build_line_item_fingerprint,
)


@dataclass(frozen=True, slots=True)
class DuplicateInvoiceRecord:
    id: UUID
    vendor_id: UUID | None
    invoice_number: str | None
    invoice_date: date | None
    total_amount: Decimal | None


class DuplicateDetectionRepository(BaseRepository):
    async def get_invoice_by_id(
        self,
        invoice_id: UUID,
    ) -> DuplicateInvoiceRecord | None:
        stmt = select(
            Invoice.id,
            Invoice.vendor_id,
            Invoice.invoice_number,
            Invoice.invoice_date,
            Invoice.total_amount,
        ).where(
            Invoice.id == invoice_id,
        )

        result = await self.execute(
            stmt,
        )
        row = result.one_or_none()

        if row is None:
            return None

        return self._to_record(
            row,
        )

    async def find_by_vendor_and_invoice_number(
        self,
        vendor_id: UUID,
        invoice_number: str,
        *,
        exclude_invoice_id: UUID,
    ) -> list[DuplicateInvoiceRecord]:
        stmt = select(
            Invoice.id,
            Invoice.vendor_id,
            Invoice.invoice_number,
            Invoice.invoice_date,
            Invoice.total_amount,
        ).where(
            Invoice.vendor_id == vendor_id,
            Invoice.invoice_number == invoice_number.strip(),
            Invoice.id != exclude_invoice_id,
        )

        result = await self.execute(
            stmt,
        )

        return [
            self._to_record(
                row,
            )
            for row in result.all()
        ]

    async def find_by_vendor_id(
        self,
        vendor_id: UUID,
        *,
        exclude_invoice_id: UUID,
    ) -> list[DuplicateInvoiceRecord]:
        stmt = select(
            Invoice.id,
            Invoice.vendor_id,
            Invoice.invoice_number,
            Invoice.invoice_date,
            Invoice.total_amount,
        ).where(
            Invoice.vendor_id == vendor_id,
            Invoice.id != exclude_invoice_id,
        )

        result = await self.execute(
            stmt,
        )

        return [
            self._to_record(
                row,
            )
            for row in result.all()
        ]

    async def get_business_content(
        self,
        invoice_id: UUID,
    ) -> InvoiceBusinessContent:
        invoice = await self.get_invoice_by_id(
            invoice_id,
        )
        line_items = await self._get_line_item_fingerprints(
            invoice_id,
        )
        total_amount = await self._get_total_amount(
            invoice_id,
        )

        return InvoiceBusinessContent(
            invoice_date=(
                invoice.invoice_date
                if invoice is not None
                else None
            ),
            line_items=line_items,
            total_amount=total_amount,
        )

    async def _get_line_item_fingerprints(
        self,
        invoice_id: UUID,
    ) -> frozenset[tuple[str, str, Decimal, Decimal]]:
        stmt = (
            select(
                InvoiceLineItem.item_code,
                InvoiceLineItem.item_description,
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

        return frozenset(
            build_line_item_fingerprint(
                item_code=row.item_code,
                item_description=row.item_description,
                quantity_billed=row.quantity_billed,
                unit_price=row.unit_price,
            )
            for row in result.all()
        )

    async def _get_total_amount(
        self,
        invoice_id: UUID,
    ) -> Decimal | None:
        stmt = select(
            Invoice.total_amount,
        ).where(
            Invoice.id == invoice_id,
        )

        result = await self.execute(
            stmt,
        )
        value = result.scalar_one_or_none()

        if value is None:
            return None

        return value.quantize(
            Decimal("0.01"),
        )

    @staticmethod
    def _to_record(
        row: object,
    ) -> DuplicateInvoiceRecord:
        total_amount = row.total_amount

        return DuplicateInvoiceRecord(
            id=row.id,
            vendor_id=row.vendor_id,
            invoice_number=row.invoice_number,
            invoice_date=row.invoice_date,
            total_amount=(
                total_amount.quantize(
                    Decimal("0.01"),
                )
                if total_amount is not None
                else None
            ),
        )
