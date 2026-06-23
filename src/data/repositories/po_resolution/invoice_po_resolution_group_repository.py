from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, select, update

from src.data.models.postgres.enums import POResolutionCandidateType
from src.data.models.postgres.invoice_po_resolution_groups import (
    InvoicePOResolutionGroup,
    InvoicePOResolutionGroupItem,
)
from src.data.repositories.base_repo import BaseRepository


@dataclass(frozen=True, slots=True)
class ResolutionGroupCreate:
    candidate_type: POResolutionCandidateType
    po_ids: list[UUID]
    confidence_score: Decimal | None = None
    is_selected: bool = False


@dataclass(frozen=True, slots=True)
class ResolutionGroupRecord:
    id: UUID
    invoice_id: UUID
    candidate_type: POResolutionCandidateType
    confidence_score: Decimal | None
    is_selected: bool
    po_ids: list[UUID]


class InvoicePOResolutionGroupRepository(BaseRepository):
    async def delete_groups_for_invoice(
        self,
        invoice_id: UUID,
    ) -> None:
        stmt = delete(
            InvoicePOResolutionGroup,
        ).where(
            InvoicePOResolutionGroup.invoice_id == invoice_id,
        )
        await self.execute(stmt)

    async def replace_groups_for_invoice(
        self,
        invoice_id: UUID,
        groups: list[ResolutionGroupCreate],
    ) -> list[ResolutionGroupRecord]:
        await self.delete_groups_for_invoice(
            invoice_id,
        )

        records: list[ResolutionGroupRecord] = []

        for group in groups:
            resolution_group = InvoicePOResolutionGroup(
                invoice_id=invoice_id,
                candidate_type=group.candidate_type,
                confidence_score=group.confidence_score,
                is_selected=group.is_selected,
            )
            self.session.add(
                resolution_group,
            )
            await self.session.flush()

            for po_id in group.po_ids:
                self.session.add(
                    InvoicePOResolutionGroupItem(
                        resolution_group_id=resolution_group.id,
                        po_id=po_id,
                    ),
                )

            records.append(
                ResolutionGroupRecord(
                    id=resolution_group.id,
                    invoice_id=invoice_id,
                    candidate_type=group.candidate_type,
                    confidence_score=group.confidence_score,
                    is_selected=group.is_selected,
                    po_ids=list(
                        group.po_ids,
                    ),
                ),
            )

        await self.session.flush()
        return records

    async def get_groups_for_invoice(
        self,
        invoice_id: UUID,
    ) -> list[ResolutionGroupRecord]:
        stmt = (
            select(
                InvoicePOResolutionGroup,
            )
            .where(
                InvoicePOResolutionGroup.invoice_id == invoice_id,
            )
            .order_by(
                InvoicePOResolutionGroup.created_at,
            )
        )
        result = await self.execute(
            stmt,
        )
        groups = result.scalars().all()

        records: list[ResolutionGroupRecord] = []

        for group in groups:
            item_stmt = select(
                InvoicePOResolutionGroupItem.po_id,
            ).where(
                InvoicePOResolutionGroupItem.resolution_group_id
                == group.id,
            )
            item_result = await self.execute(
                item_stmt,
            )
            po_ids = list(
                item_result.scalars().all(),
            )
            records.append(
                ResolutionGroupRecord(
                    id=group.id,
                    invoice_id=group.invoice_id,
                    candidate_type=group.candidate_type,
                    confidence_score=group.confidence_score,
                    is_selected=group.is_selected,
                    po_ids=po_ids,
                ),
            )

        return records

    async def get_candidate_po_ids_for_validation(
        self,
        invoice_id: UUID,
    ) -> list[UUID]:
        groups = await self.get_groups_for_invoice(
            invoice_id,
        )

        if len(groups) != 1:
            return []

        group = groups[0]

        if group.candidate_type not in (
            POResolutionCandidateType.RESOLVED,
            POResolutionCandidateType.RECOVERED,
        ):
            return []

        return group.po_ids

    async def select_group(
        self,
        invoice_id: UUID,
        group_id: UUID,
    ) -> ResolutionGroupRecord | None:
        await self.execute(
            update(
                InvoicePOResolutionGroup,
            )
            .where(
                InvoicePOResolutionGroup.invoice_id == invoice_id,
            )
            .values(
                is_selected=False,
            ),
        )
        await self.execute(
            update(
                InvoicePOResolutionGroup,
            )
            .where(
                InvoicePOResolutionGroup.id == group_id,
                InvoicePOResolutionGroup.invoice_id == invoice_id,
            )
            .values(
                is_selected=True,
            ),
        )

        groups = await self.get_groups_for_invoice(
            invoice_id,
        )

        for group in groups:
            if group.id == group_id:
                return group

        return None
