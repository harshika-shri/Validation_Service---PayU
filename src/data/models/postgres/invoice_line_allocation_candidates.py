from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.postgres.base import Base
from src.data.models.postgres.enums import POResolutionCandidateType
from src.data.models.postgres.mixins import CreatedAtMixin
from src.data.models.postgres.types import pg_enum


class InvoiceLineAllocationCandidateGroup(Base, CreatedAtMixin):
    __tablename__ = "invoice_line_allocation_candidate_groups"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    invoice_id: Mapped[UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
    )

    resolution_group_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "invoice_po_resolution_groups.id",
            ondelete="SET NULL",
        ),
        nullable=True,
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

    items: Mapped[list[InvoiceLineAllocationCandidateItem]] = relationship(
        back_populates="allocation_candidate_group",
        cascade="all, delete-orphan",
    )


class InvoiceLineAllocationCandidateItem(Base, CreatedAtMixin):
    __tablename__ = "invoice_line_allocation_candidate_items"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    allocation_candidate_group_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "invoice_line_allocation_candidate_groups.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    invoice_line_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("invoice_line_items.id", ondelete="CASCADE"),
        nullable=False,
    )

    po_line_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("po_line_items.id", ondelete="CASCADE"),
        nullable=False,
    )

    allocated_quantity: Mapped[Decimal] = mapped_column(
        Numeric(15, 3),
        nullable=False,
    )

    allocated_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
    )

    candidate_type: Mapped[POResolutionCandidateType] = mapped_column(
        pg_enum(POResolutionCandidateType),
        nullable=False,
    )

    allocation_candidate_group: Mapped[InvoiceLineAllocationCandidateGroup] = (
        relationship(
            back_populates="items",
        )
    )
