from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.data.models.postgres.base import Base
from src.data.models.postgres.enums import PurchaseOrderStatus
from src.data.models.postgres.mixins import TimestampMixin
from src.data.models.postgres.types import pg_enum


class PurchaseOrder(Base, TimestampMixin):
    __tablename__ = "purchase_orders"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    po_number: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    vendor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("vendor_master.id"),
        nullable=True,
    )

    company_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("company_master.id"),
        nullable=True,
    )

    delivery_address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        default="INR",
        nullable=False,
    )

    payment_terms: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    po_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    valid_until: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    subtotal_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
    )

    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        default=0,
    )

    tax_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
    )

    total_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
    )

    consumed_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=0,
    )

    status: Mapped[PurchaseOrderStatus] = mapped_column(
        pg_enum(PurchaseOrderStatus),
        nullable=False,
    )

    gcs_file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    uploaded_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )
