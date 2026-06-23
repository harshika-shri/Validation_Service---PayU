from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.postgres.base import Base
from src.data.models.postgres.enums import POResolutionCandidateType
from src.data.models.postgres.mixins import CreatedAtMixin
from src.data.models.postgres.types import pg_enum


class InvoicePOResolutionGroup(Base, CreatedAtMixin):
    __tablename__ = "invoice_po_resolution_groups"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    invoice_id: Mapped[UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
    )

    candidate_type: Mapped[POResolutionCandidateType] = mapped_column(
        pg_enum(POResolutionCandidateType),
        nullable=False,
    )

    confidence_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    is_selected: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    items: Mapped[list[InvoicePOResolutionGroupItem]] = relationship(
        back_populates="resolution_group",
        cascade="all, delete-orphan",
    )


class InvoicePOResolutionGroupItem(Base):
    __tablename__ = "invoice_po_resolution_group_items"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    resolution_group_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "invoice_po_resolution_groups.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    po_id: Mapped[UUID] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="CASCADE"),
        nullable=False,
    )

    resolution_group: Mapped[InvoicePOResolutionGroup] = relationship(
        back_populates="items",
    )
