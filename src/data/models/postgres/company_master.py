from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.data.models.postgres.base import Base
from src.data.models.postgres.enums import CompanyStatus
from src.data.models.postgres.mixins import TimestampMixin


class CompanyMaster(Base, TimestampMixin):
    __tablename__ = "company_master"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    company_name: Mapped[str] = mapped_column(String(255), nullable=False)

    company_code: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    gstin: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    pan_number: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    billing_address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    shipping_address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[CompanyStatus] = mapped_column(
        Enum(CompanyStatus),
        nullable=False,
        default=CompanyStatus.ACTIVE,
    )
