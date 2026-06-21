from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.data.models.postgres.base import Base
from src.data.models.postgres.mixins import CreatedAtMixin


class InvoiceLineItem(Base, CreatedAtMixin):
    __tablename__ = "invoice_line_items"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    invoice_id: Mapped[UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
    )

    po_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("purchase_orders.id"),
        nullable=True,
    )

    line_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    item_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    item_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    uom: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    quantity_billed: Mapped[Decimal] = mapped_column(
        Numeric(15, 3),
        nullable=False,
    )

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
    )

    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        default=0,
        nullable=True,
    )

    tax_details: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    hsn_sac_code: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    line_total: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
    )

    is_item_code_matched: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=True,
    )

    is_unauthorized_extra_item: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=True,
    )

    is_hsn_matched: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=True,
    )

    is_line_total_correct: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=True,
    )

    is_unit_price_matched: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=True,
    )

    is_quantity_valid: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=True,
    )

    is_uom_matched: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=True,
    )

    is_tax_correct: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=True,
    )
