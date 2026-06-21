from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.data.models.postgres.base import Base
from src.data.models.postgres.mixins import CreatedAtMixin


class InvoiceExtractedVendor(Base, CreatedAtMixin):
    __tablename__ = "invoice_extracted_vendor"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    invoice_id: Mapped[UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    vendor_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    vendor_gstin: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    vendor_address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    vendor_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    vendor_phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    bank_account_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    bank_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    ifsc_code: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    account_holder_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    vendor_master_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("vendor_master.id"),
        nullable=True,
    )

    is_vendor_name_matched: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=True,
    )

    is_gstin_matched: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=True,
    )

    is_bank_matched: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=True,
    )

    is_ifsc_matched: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=True,
    )

    is_vendor_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=True,
    )
