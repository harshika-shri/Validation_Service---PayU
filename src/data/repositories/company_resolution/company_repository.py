from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select

from src.data.models.postgres.company_master import CompanyMaster
from src.data.models.postgres.enums import CompanyStatus
from src.data.models.postgres.invoices import Invoice
from src.data.repositories.base_repo import BaseRepository


@dataclass(frozen=True, slots=True)
class CompanyRecord:
    id: UUID
    company_name: str
    gstin: str
    pan_number: str | None
    email: str | None
    phone: str | None
    billing_address: str | None
    shipping_address: str | None


class CompanyRepository(BaseRepository):
    async def get_active_company(
        self,
    ) -> CompanyRecord | None:
        stmt = (
            select(
                CompanyMaster.id,
                CompanyMaster.company_name,
                CompanyMaster.gstin,
                CompanyMaster.pan_number,
                CompanyMaster.email,
                CompanyMaster.phone,
                CompanyMaster.billing_address,
                CompanyMaster.shipping_address,
            )
            .where(
                CompanyMaster.status == CompanyStatus.ACTIVE,
            )
            .limit(1)
        )

        result = await self.execute(
            stmt,
        )
        row = result.one_or_none()

        if row is None:
            return None

        return CompanyRecord(
            id=row.id,
            company_name=row.company_name,
            gstin=row.gstin,
            pan_number=row.pan_number,
            email=row.email,
            phone=row.phone,
            billing_address=row.billing_address,
            shipping_address=row.shipping_address,
        )

    async def get_by_id(
        self,
        company_id: UUID,
    ) -> CompanyRecord | None:
        stmt = (
            select(
                CompanyMaster.id,
                CompanyMaster.company_name,
                CompanyMaster.gstin,
                CompanyMaster.pan_number,
                CompanyMaster.email,
                CompanyMaster.phone,
                CompanyMaster.billing_address,
                CompanyMaster.shipping_address,
            )
            .where(
                CompanyMaster.id == company_id,
                CompanyMaster.status == CompanyStatus.ACTIVE,
            )
            .limit(1)
        )

        result = await self.execute(
            stmt,
        )
        row = result.one_or_none()

        if row is None:
            return None

        return CompanyRecord(
            id=row.id,
            company_name=row.company_name,
            gstin=row.gstin,
            pan_number=row.pan_number,
            email=row.email,
            phone=row.phone,
            billing_address=row.billing_address,
            shipping_address=row.shipping_address,
        )

    async def get_for_invoice(
        self,
        invoice_id: UUID,
    ) -> CompanyRecord | None:
        stmt = select(
            Invoice.company_id,
        ).where(
            Invoice.id == invoice_id,
        )

        result = await self.execute(
            stmt,
        )
        company_id = result.scalar_one_or_none()

        if company_id is not None:
            company = await self.get_by_id(
                company_id,
            )

            if company is not None:
                return company

        return await self.get_active_company()
