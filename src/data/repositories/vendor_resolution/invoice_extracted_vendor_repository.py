from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select, update

from src.data.models.postgres.invoice_extracted_vendor import (
    InvoiceExtractedVendor,
)
from src.data.repositories.base_repo import BaseRepository


@dataclass(frozen=True, slots=True)
class ExtractedVendorRecord:
    invoice_id: UUID
    vendor_master_id: UUID | None
    vendor_name: str | None
    vendor_gstin: str | None
    vendor_phone: str | None
    bank_account_number: str | None
    bank_name: str | None
    ifsc_code: str | None
    address: str | None


class InvoiceExtractedVendorRepository(BaseRepository):
    async def get_by_invoice_id(
        self,
        invoice_id: UUID,
    ) -> ExtractedVendorRecord | None:
        stmt = select(
            InvoiceExtractedVendor.invoice_id,
            InvoiceExtractedVendor.vendor_name,
            InvoiceExtractedVendor.vendor_gstin,
            InvoiceExtractedVendor.vendor_phone,
            InvoiceExtractedVendor.bank_account_number,
            InvoiceExtractedVendor.bank_name,
            InvoiceExtractedVendor.ifsc_code,
            InvoiceExtractedVendor.vendor_address,
            InvoiceExtractedVendor.vendor_master_id,
        ).where(
            InvoiceExtractedVendor.invoice_id == invoice_id,
        )

        result = await self.execute(
            stmt,
        )
        row = result.one_or_none()

        if row is None:
            return None

        return ExtractedVendorRecord(
            invoice_id=row.invoice_id,
            vendor_master_id=row.vendor_master_id,
            vendor_name=row.vendor_name,
            vendor_gstin=row.vendor_gstin,
            vendor_phone=row.vendor_phone,
            bank_account_number=row.bank_account_number,
            bank_name=row.bank_name,
            ifsc_code=row.ifsc_code,
            address=row.vendor_address,
        )

    async def update_vendor_master_id(
        self,
        invoice_id: UUID,
        vendor_master_id: UUID,
    ) -> None:
        stmt = (
            update(
                InvoiceExtractedVendor,
            )
            .where(
                InvoiceExtractedVendor.invoice_id == invoice_id,
            )
            .values(
                vendor_master_id=vendor_master_id,
            )
        )

        await self.execute(
            stmt,
        )
