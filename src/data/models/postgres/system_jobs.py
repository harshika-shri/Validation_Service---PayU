from __future__ import annotations

from datetime import date

from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column

from src.data.models.postgres.base import Base
from src.data.models.postgres.mixins import TimestampMixin


class SystemJob(Base, TimestampMixin):
    __tablename__ = "system_jobs"

    job_name: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )

    last_run_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
