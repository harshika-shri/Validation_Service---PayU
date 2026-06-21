from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.data.models.postgres.base import Base
from src.data.models.postgres.mixins import CreatedAtMixin


class InvoicePOMapping(Base, CreatedAtMixin):
    __tablename__ = "invoice_po_mapping"

    __table_args__ = (
        UniqueConstraint(
            "invoice_id",
            "po_id",
            name="uq_invoice_po_mapping",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    invoice_id: Mapped[UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
    )

    po_id: Mapped[UUID] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
