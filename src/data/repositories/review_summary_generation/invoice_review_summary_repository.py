from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select, update

from src.data.models.postgres.invoice_review_summaries import (
    InvoiceReviewSummary,
)
from src.data.repositories.base_repo import BaseRepository


@dataclass(frozen=True, slots=True)
class ReviewSummaryRecord:
    id: UUID
    invoice_id: UUID
    decision: str
    executive_summary: str
    system_recoveries: list[str]
    open_issues: list[str]
    vendor_clarifications: list[str]
    validation_steps: dict[str, str]


@dataclass(frozen=True, slots=True)
class ReviewSummaryUpsert:
    decision: str
    executive_summary: str
    system_recoveries: list[str]
    open_issues: list[str]
    vendor_clarifications: list[str]
    validation_steps: dict[str, str]


class InvoiceReviewSummaryRepository(BaseRepository):
    async def upsert(
        self,
        invoice_id: UUID,
        summary: ReviewSummaryUpsert,
    ) -> ReviewSummaryRecord:
        existing = await self.get_by_invoice_id(
            invoice_id,
        )

        if existing is None:
            record = InvoiceReviewSummary(
                invoice_id=invoice_id,
                decision=summary.decision,
                executive_summary=summary.executive_summary,
                system_recoveries_json=summary.system_recoveries,
                open_issues_json=summary.open_issues,
                vendor_clarifications_json=summary.vendor_clarifications,
                validation_steps_json=summary.validation_steps,
            )
            self.session.add(
                record,
            )
            await self.session.flush()
            await self.session.refresh(
                record,
            )

            return self._to_record(
                record,
            )

        stmt = (
            update(
                InvoiceReviewSummary,
            )
            .where(
                InvoiceReviewSummary.invoice_id == invoice_id,
            )
            .values(
                decision=summary.decision,
                executive_summary=summary.executive_summary,
                system_recoveries_json=summary.system_recoveries,
                open_issues_json=summary.open_issues,
                vendor_clarifications_json=summary.vendor_clarifications,
                validation_steps_json=summary.validation_steps,
            )
            .returning(
                InvoiceReviewSummary,
            )
        )
        result = await self.execute(
            stmt,
        )
        record = result.scalar_one()

        return self._to_record(
            record,
        )

    async def get_by_invoice_id(
        self,
        invoice_id: UUID,
    ) -> ReviewSummaryRecord | None:
        stmt = select(
            InvoiceReviewSummary,
        ).where(
            InvoiceReviewSummary.invoice_id == invoice_id,
        )

        result = await self.execute(
            stmt,
        )
        record = result.scalar_one_or_none()

        if record is None:
            return None

        return self._to_record(
            record,
        )

    @staticmethod
    def _to_record(
        record: InvoiceReviewSummary,
    ) -> ReviewSummaryRecord:
        return ReviewSummaryRecord(
            id=record.id,
            invoice_id=record.invoice_id,
            decision=record.decision,
            executive_summary=record.executive_summary,
            system_recoveries=list(
                record.system_recoveries_json,
            ),
            open_issues=list(
                record.open_issues_json,
            ),
            vendor_clarifications=list(
                record.vendor_clarifications_json,
            ),
            validation_steps=dict(
                record.validation_steps_json or {},
            ),
        )
