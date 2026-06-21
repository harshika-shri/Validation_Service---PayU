from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import select, update

from src.data.models.postgres.enums import InvoiceStatus
from src.data.models.postgres.invoices import Invoice
from src.data.models.postgres.vendor_master import VendorMaster
from src.data.repositories.base_repo import BaseRepository


@dataclass(frozen=True, slots=True)
class InvoiceRecord:
    id: UUID
    invoice_number: str | None
    invoice_date: date | None


@dataclass(frozen=True, slots=True)
class ReviewSummaryInvoiceRecord:
    id: UUID
    invoice_number: str | None
    vendor_id: UUID | None
    invoice_status: InvoiceStatus | None
    vendor_name: str | None


@dataclass(frozen=True, slots=True)
class BuyerCompanyExtractedRecord:
    company_name: str | None
    gstin: str | None
    pan_number: str | None
    email: str | None
    phone: str | None
    billing_address: str | None
    shipping_address: str | None
    bank_account_number: str | None
    bank_name: str | None
    ifsc_code: str | None


class InvoiceRepository(BaseRepository):
    async def get_invoice_by_id(
        self,
        invoice_id: UUID,
    ) -> InvoiceRecord | None:
        stmt = select(
            Invoice.id,
            Invoice.invoice_number,
            Invoice.invoice_date,
        ).where(
            Invoice.id == invoice_id,
        )

        result = await self.execute(stmt)
        row = result.one_or_none()

        if row is None:
            return None

        return InvoiceRecord(
            id=row.id,
            invoice_number=row.invoice_number,
            invoice_date=row.invoice_date,
        )

    async def get_review_summary_invoice(
        self,
        invoice_id: UUID,
    ) -> ReviewSummaryInvoiceRecord | None:
        stmt = (
            select(
                Invoice.id,
                Invoice.invoice_number,
                Invoice.vendor_id,
                Invoice.invoice_status,
                VendorMaster.vendor_name,
            )
            .outerjoin(
                VendorMaster,
                VendorMaster.id == Invoice.vendor_id,
            )
            .where(
                Invoice.id == invoice_id,
            )
        )

        result = await self.execute(
            stmt,
        )
        row = result.one_or_none()

        if row is None:
            return None

        return ReviewSummaryInvoiceRecord(
            id=row.id,
            invoice_number=row.invoice_number,
            vendor_id=row.vendor_id,
            invoice_status=row.invoice_status,
            vendor_name=row.vendor_name,
        )

    async def get_buyer_company_details(
        self,
        invoice_id: UUID,
    ) -> BuyerCompanyExtractedRecord | None:
        stmt = select(
            Invoice.company_name,
            Invoice.company_gstin,
            Invoice.company_address,
        ).where(
            Invoice.id == invoice_id,
        )

        result = await self.execute(
            stmt,
        )
        row = result.one_or_none()

        if row is None:
            return None

        return BuyerCompanyExtractedRecord(
            company_name=row.company_name,
            gstin=row.company_gstin,
            pan_number=None,
            email=None,
            phone=None,
            billing_address=row.company_address,
            shipping_address=None,
            bank_account_number=None,
            bank_name=None,
            ifsc_code=None,
        )

    async def update_invoice_number(
        self,
        invoice_id: UUID,
        invoice_number: str,
    ) -> None:
        stmt = (
            update(Invoice)
            .where(
                Invoice.id == invoice_id,
            )
            .values(
                invoice_number=invoice_number,
            )
        )

        await self.execute(stmt)

    async def update_invoice_status(
        self,
        invoice_id: UUID,
        invoice_status: InvoiceStatus,
    ) -> None:
        stmt = (
            update(Invoice)
            .where(
                Invoice.id == invoice_id,
            )
            .values(
                invoice_status=invoice_status,
            )
        )

        await self.execute(
            stmt,
        )

    async def update_invoice_date(
        self,
        invoice_id: UUID,
        invoice_date: date,
    ) -> None:
        stmt = (
            update(Invoice)
            .where(
                Invoice.id == invoice_id,
            )
            .values(
                invoice_date=invoice_date,
            )
        )

        await self.execute(stmt)
