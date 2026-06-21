from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.data.models.postgres.base import Base
from src.data.models.postgres.enums import (
    IssueType,
    ValidationIssueStatus,
)
from src.data.models.postgres.mixins import TimestampMixin
from src.data.models.postgres.types import pg_enum


class InvoiceValidationIssue(Base, TimestampMixin):
    __tablename__ = "invoice_validation_issues"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    invoice_id: Mapped[UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
    )

    check_stage: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    check_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    field_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    field_path: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    issue_type: Mapped[IssueType] = mapped_column(
        pg_enum(IssueType),
        nullable=False,
    )

    expected_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    actual_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[ValidationIssueStatus] = mapped_column(
        pg_enum(ValidationIssueStatus),
        nullable=False,
        default=ValidationIssueStatus.OPEN,
    )

    issue_metadata: Mapped[dict | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )
