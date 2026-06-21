from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from src.data.models.postgres.invoice_emails import InvoiceEmail
from src.data.repositories.base_repo import BaseRepository


@dataclass(frozen=True, slots=True)
class InvoiceEmailRecord:
    subject: str | None
    body_text: str | None
    email_sent_date: datetime | None


class InvoiceEmailRepository(BaseRepository):
    async def get_invoice_email(
        self,
        invoice_id: UUID,
    ) -> InvoiceEmailRecord | None:
        stmt = select(
            InvoiceEmail.subject,
            InvoiceEmail.body_text,
            InvoiceEmail.created_at,
        ).where(
            InvoiceEmail.invoice_id == invoice_id,
        )

        result = await self.execute(stmt)
        row = result.one_or_none()

        if row is None:
            return None

        return InvoiceEmailRecord(
            subject=row.subject,
            body_text=row.body_text,
            email_sent_date=row.created_at,
        )
