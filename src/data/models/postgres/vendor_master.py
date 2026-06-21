from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from src.data.models.postgres.base import Base
from src.data.models.postgres.enums import VendorStatus
from src.data.models.postgres.mixins import TimestampMixin


class VendorMaster(Base, TimestampMixin):
    __tablename__ = "vendor_master"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    vendor_code: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    vendor_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    gstin: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
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

    address_line_1: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    address_line_2: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    city: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    state: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    bank_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    account_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    ifsc_code: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    account_holder_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    status: Mapped[VendorStatus] = mapped_column(
        Enum(VendorStatus),
        nullable=False,
    )
