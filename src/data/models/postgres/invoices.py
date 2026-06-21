from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.data.models.postgres.base import Base
from src.data.models.postgres.enums import ExtractionStatus, InvoiceStatus
from src.data.models.postgres.mixins import TimestampMixin
from src.data.models.postgres.types import pg_enum


class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    company_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("company_master.id"),
        nullable=True,
    )

    invoice_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    invoice_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    due_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    po_numbers_extracted: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        default="INR",
        nullable=True,
    )

    payment_terms: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    subtotal_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )

    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=True,
    )

    tax_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )

    total_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    company_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    company_gstin: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    company_address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    vendor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("vendor_master.id"),
        nullable=True,
    )

    gcs_file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    received_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    extraction_status: Mapped[ExtractionStatus] = mapped_column(
        Enum(ExtractionStatus),
        nullable=False,
    )

    invoice_status: Mapped[InvoiceStatus | None] = mapped_column(
        pg_enum(InvoiceStatus),
        nullable=True,
    )

    is_high_value: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=True,
    )

    is_partial_invoice: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=True,
    )

    assigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    escalated_to: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    hold_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    paid_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )
