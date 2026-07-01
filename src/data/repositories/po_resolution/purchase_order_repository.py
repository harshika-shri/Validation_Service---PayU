from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select

from src.data.models.postgres.enums import PurchaseOrderStatus
from src.data.models.postgres.purchase_orders import PurchaseOrder
from src.data.repositories.base_repo import BaseRepository
from src.utils.po_number_utils import (
    normalize_po_number_for_lookup,
)


@dataclass(frozen=True, slots=True)
class PurchaseOrderRecord:
    id: UUID
    po_number: str
    vendor_id: UUID | None
    po_date: date
    valid_until: date | None
    status: PurchaseOrderStatus
    total_amount: Decimal | None
    subtotal_amount: Decimal | None
    tax_amount: Decimal | None
    discount_amount: Decimal | None


class PurchaseOrderRepository(BaseRepository):
    async def find_by_po_number(
        self,
        po_number: str,
    ) -> PurchaseOrderRecord | None:
        normalized = normalize_po_number_for_lookup(
            po_number,
        )

        if not normalized:
            return None

        stmt = select(
            PurchaseOrder.id,
            PurchaseOrder.po_number,
            PurchaseOrder.vendor_id,
            PurchaseOrder.po_date,
            PurchaseOrder.valid_until,
            PurchaseOrder.status,
            PurchaseOrder.total_amount,
            PurchaseOrder.subtotal_amount,
            PurchaseOrder.tax_amount,
            PurchaseOrder.discount_amount,
        ).where(
            func.lower(
                PurchaseOrder.po_number,
            )
            == normalized.casefold(),
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

    async def find_by_vendor_and_statuses(
        self,
        vendor_id: UUID,
        statuses: list[PurchaseOrderStatus],
    ) -> list[PurchaseOrderRecord]:
        stmt = select(
            PurchaseOrder.id,
            PurchaseOrder.po_number,
            PurchaseOrder.vendor_id,
            PurchaseOrder.po_date,
            PurchaseOrder.valid_until,
            PurchaseOrder.status,
            PurchaseOrder.total_amount,
            PurchaseOrder.subtotal_amount,
            PurchaseOrder.tax_amount,
            PurchaseOrder.discount_amount,
        ).where(
            PurchaseOrder.vendor_id == vendor_id,
            PurchaseOrder.status.in_(
                statuses,
            ),
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

    async def get_by_ids(
        self,
        po_ids: list[UUID],
    ) -> list[PurchaseOrderRecord]:
        if not po_ids:
            return []

        stmt = select(
            PurchaseOrder.id,
            PurchaseOrder.po_number,
            PurchaseOrder.vendor_id,
            PurchaseOrder.po_date,
            PurchaseOrder.valid_until,
            PurchaseOrder.status,
            PurchaseOrder.total_amount,
            PurchaseOrder.subtotal_amount,
            PurchaseOrder.tax_amount,
            PurchaseOrder.discount_amount,
        ).where(
            PurchaseOrder.id.in_(
                po_ids,
            ),
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

    @staticmethod
    def _to_record(
        row: object,
    ) -> PurchaseOrderRecord:
        return PurchaseOrderRecord(
            id=row.id,
            po_number=row.po_number,
            vendor_id=row.vendor_id,
            po_date=row.po_date,
            valid_until=row.valid_until,
            status=row.status,
            total_amount=row.total_amount,
            subtotal_amount=row.subtotal_amount,
            tax_amount=row.tax_amount,
            discount_amount=row.discount_amount,
        )
