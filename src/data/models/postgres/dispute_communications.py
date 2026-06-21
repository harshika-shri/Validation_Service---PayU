from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.data.models.postgres.base import Base
from src.data.models.postgres.enums import CommunicationStatus
from src.data.models.postgres.mixins import CreatedAtMixin


class DisputeCommunication(Base, CreatedAtMixin):
    __tablename__ = "dispute_communications"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    dispute_id: Mapped[UUID] = mapped_column(
        ForeignKey("disputes.id", ondelete="CASCADE"),
        nullable=False,
    )

    drafted_by_ai: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    reviewed_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    recipient_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    subject: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[CommunicationStatus] = mapped_column(
        Enum(CommunicationStatus),
        nullable=False,
    )

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
