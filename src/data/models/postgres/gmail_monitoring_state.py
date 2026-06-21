from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from src.data.models.postgres.base import Base


class GmailMonitoringState(Base):
    __tablename__ = "gmail_monitoring_state"

    email_address: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
    )

    last_processed_history_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    is_monitoring: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
