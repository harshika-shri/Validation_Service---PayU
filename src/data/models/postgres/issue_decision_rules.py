from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.data.models.postgres.base import Base
from src.data.models.postgres.enums import IssueDecisionCategory
from src.data.models.postgres.mixins import CreatedAtMixin


class IssueDecisionRule(Base, CreatedAtMixin):
    __tablename__ = "issue_decision_rules"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    issue_code: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    decision_category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=IssueDecisionCategory.APPROVE.value,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
