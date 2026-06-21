from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select

from src.data.models.postgres.invoice_po_mapping import InvoicePOMapping
from src.data.repositories.base_repo import BaseRepository


class InvoicePOMappingRepository(BaseRepository):
    async def get_po_ids_by_invoice_id(
        self,
        invoice_id: UUID,
    ) -> list[UUID]:
        stmt = select(
            InvoicePOMapping.po_id,
        ).where(
            InvoicePOMapping.invoice_id == invoice_id,
        )

        result = await self.execute(
            stmt,
        )

        return list(
            result.scalars().all(),
        )

    async def create_mappings(
        self,
        invoice_id: UUID,
        po_ids: list[UUID],
    ) -> None:
        existing_po_ids = set(
            await self.get_po_ids_by_invoice_id(
                invoice_id,
            ),
        )
        created = False

        for po_id in po_ids:
            if po_id in existing_po_ids:
                continue

            mapping = InvoicePOMapping(
                invoice_id=invoice_id,
                po_id=po_id,
            )
            self.session.add(
                mapping,
            )
            created = True

        if created:
            await self.session.flush()

    async def delete_mappings_for_invoice(
        self,
        invoice_id: UUID,
    ) -> None:
        stmt = delete(
            InvoicePOMapping,
        ).where(
            InvoicePOMapping.invoice_id == invoice_id,
        )

        await self.execute(
            stmt,
        )
        await self.session.flush()
