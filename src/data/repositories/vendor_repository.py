from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select

from src.data.models.postgres.enums import VendorStatus
from src.data.models.postgres.vendor_master import VendorMaster
from src.data.repositories.base_repo import BaseRepository
from src.utils.company_matching_utils import (
    normalize_bank_account,
    normalize_company_name_for_exact_match,
    normalize_gstin,
    normalize_ifsc,
)


@dataclass(frozen=True, slots=True)
class VendorRecord:
    id: UUID
    vendor_name: str
    vendor_code: str
    gstin: str | None
    phone: str | None
    bank_account_number: str | None
    bank_name: str | None
    ifsc_code: str | None
    address: str | None
    status: VendorStatus


def format_vendor_address(
    address_line_1: str | None,
    address_line_2: str | None,
    city: str | None,
    state: str | None,
) -> str | None:
    parts = [
        address_line_1,
        address_line_2,
        city,
        state,
    ]
    filtered = [
        part.strip()
        for part in parts
        if part is not None and part.strip()
    ]

    if not filtered:
        return None

    return ", ".join(
        filtered,
    )


class VendorRepository(BaseRepository):
    async def find_by_gstin(
        self,
        gstin: str,
    ) -> list[VendorRecord]:
        normalized_gstin = normalize_gstin(
            gstin,
        )
        stmt = select(
            VendorMaster.id,
            VendorMaster.vendor_name,
            VendorMaster.vendor_code,
            VendorMaster.gstin,
            VendorMaster.phone,
            VendorMaster.account_number,
            VendorMaster.bank_name,
            VendorMaster.ifsc_code,
            VendorMaster.address_line_1,
            VendorMaster.address_line_2,
            VendorMaster.city,
            VendorMaster.state,
            VendorMaster.status,
        ).where(
            VendorMaster.gstin.is_not(
                None,
            ),
        )

        result = await self.execute(
            stmt,
        )
        rows = result.all()

        return [
            self._to_vendor_record(
                row,
            )
            for row in rows
            if row.gstin is not None
            and normalize_gstin(
                row.gstin,
            )
            == normalized_gstin
        ]

    async def find_by_bank_account_and_ifsc(
        self,
        bank_account_number: str,
        ifsc_code: str,
    ) -> list[VendorRecord]:
        normalized_account = normalize_bank_account(
            bank_account_number,
        )
        normalized_ifsc = normalize_ifsc(
            ifsc_code,
        )
        stmt = select(
            VendorMaster.id,
            VendorMaster.vendor_name,
            VendorMaster.vendor_code,
            VendorMaster.gstin,
            VendorMaster.phone,
            VendorMaster.account_number,
            VendorMaster.bank_name,
            VendorMaster.ifsc_code,
            VendorMaster.address_line_1,
            VendorMaster.address_line_2,
            VendorMaster.city,
            VendorMaster.state,
            VendorMaster.status,
        ).where(
            VendorMaster.account_number.is_not(
                None,
            ),
            VendorMaster.ifsc_code.is_not(
                None,
            ),
        )

        result = await self.execute(
            stmt,
        )
        rows = result.all()

        return [
            self._to_vendor_record(
                row,
            )
            for row in rows
            if row.account_number is not None
            and row.ifsc_code is not None
            and normalize_bank_account(
                row.account_number,
            )
            == normalized_account
            and normalize_ifsc(
                row.ifsc_code,
            )
            == normalized_ifsc
        ]

    async def find_by_exact_vendor_name(
        self,
        vendor_name: str,
    ) -> list[VendorRecord]:
        normalized_name = normalize_company_name_for_exact_match(
            vendor_name,
        )
        vendors = await self.get_all_vendors()

        return [
            vendor
            for vendor in vendors
            if normalize_company_name_for_exact_match(
                vendor.vendor_name,
            )
            == normalized_name
        ]

    async def get_active_vendors(
        self,
    ) -> list[VendorRecord]:
        stmt = select(
            VendorMaster.id,
            VendorMaster.vendor_name,
            VendorMaster.vendor_code,
            VendorMaster.gstin,
            VendorMaster.phone,
            VendorMaster.account_number,
            VendorMaster.bank_name,
            VendorMaster.ifsc_code,
            VendorMaster.address_line_1,
            VendorMaster.address_line_2,
            VendorMaster.city,
            VendorMaster.state,
            VendorMaster.status,
        ).where(
            VendorMaster.status == VendorStatus.ACTIVE,
        )

        result = await self.execute(
            stmt,
        )

        return [
            self._to_vendor_record(
                row,
            )
            for row in result.all()
        ]

    async def get_all_vendors(
        self,
    ) -> list[VendorRecord]:
        stmt = select(
            VendorMaster.id,
            VendorMaster.vendor_name,
            VendorMaster.vendor_code,
            VendorMaster.gstin,
            VendorMaster.phone,
            VendorMaster.account_number,
            VendorMaster.bank_name,
            VendorMaster.ifsc_code,
            VendorMaster.address_line_1,
            VendorMaster.address_line_2,
            VendorMaster.city,
            VendorMaster.state,
            VendorMaster.status,
        )

        result = await self.execute(
            stmt,
        )

        return [
            self._to_vendor_record(
                row,
            )
            for row in result.all()
        ]

    async def get_by_id(
        self,
        vendor_id: UUID,
    ) -> VendorRecord | None:
        stmt = select(
            VendorMaster.id,
            VendorMaster.vendor_name,
            VendorMaster.vendor_code,
            VendorMaster.gstin,
            VendorMaster.phone,
            VendorMaster.account_number,
            VendorMaster.bank_name,
            VendorMaster.ifsc_code,
            VendorMaster.address_line_1,
            VendorMaster.address_line_2,
            VendorMaster.city,
            VendorMaster.state,
            VendorMaster.status,
        ).where(
            VendorMaster.id == vendor_id,
        )

        result = await self.execute(
            stmt,
        )
        row = result.one_or_none()

        if row is None:
            return None

        return self._to_vendor_record(
            row,
        )

    @staticmethod
    def _to_vendor_record(
        row: Any,
    ) -> VendorRecord:
        return VendorRecord(
            id=row.id,
            vendor_name=row.vendor_name,
            vendor_code=row.vendor_code,
            gstin=row.gstin,
            phone=row.phone,
            bank_account_number=row.account_number,
            bank_name=row.bank_name,
            ifsc_code=row.ifsc_code,
            address=format_vendor_address(
                row.address_line_1,
                row.address_line_2,
                row.city,
                row.state,
            ),
            status=row.status,
        )
