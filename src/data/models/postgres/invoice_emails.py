from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.data.models.postgres.base import Base
from src.data.models.postgres.mixins import CreatedAtMixin


class InvoiceEmail(Base, CreatedAtMixin):
    __tablename__ = "invoice_emails"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    invoice_id: Mapped[UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    message_id: Mapped[str] = mapped_column(
        String(500),
        unique=True,
        nullable=False,
    )

    received_from: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    subject: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    body_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    attachment_filename: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    gcs_attachment_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
