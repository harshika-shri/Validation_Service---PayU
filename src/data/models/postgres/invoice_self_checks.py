from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.data.models.postgres.base import Base
from src.data.models.postgres.mixins import CreatedAtMixin


class InvoiceSelfCheck(Base, CreatedAtMixin):
    __tablename__ = "invoice_self_checks"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    invoice_id: Mapped[UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
    )

    check_stage: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    check_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    system_action: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    detected_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    expected_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
