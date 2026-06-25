from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator

from src.messaging.extraction_events import (
    EXTRACTION_EVENT_COMPLETED,
    EXTRACTION_EVENT_VERSION,
)


class ExtractionCompletedEventPayload(BaseModel):
    version: int
    event_type: str
    invoice_id: UUID
    occurred_at: datetime

    @field_validator(
        "version",
        mode="before",
    )
    @classmethod
    def parse_version(
        cls,
        value: object,
    ) -> int:
        return int(
            value,
        )

    @field_validator(
        "event_type",
    )
    @classmethod
    def validate_event_type(
        cls,
        value: str,
    ) -> str:
        if value != EXTRACTION_EVENT_COMPLETED:
            raise ValueError(
                f"Unsupported event_type: {value}",
            )

        return value

    @field_validator(
        "occurred_at",
        mode="before",
    )
    @classmethod
    def parse_occurred_at(
        cls,
        value: object,
    ) -> datetime:
        if isinstance(
            value,
            datetime,
        ):
            return value

        return datetime.fromisoformat(
            str(
                value,
            ),
        )


def parse_extraction_completed_event(
    fields: dict[str, str],
) -> ExtractionCompletedEventPayload:
    return ExtractionCompletedEventPayload(
        version=fields.get(
            "version",
            EXTRACTION_EVENT_VERSION,
        ),
        event_type=fields.get(
            "event_type",
            "",
        ),
        invoice_id=fields.get(
            "invoice_id",
            "",
        ),
        occurred_at=fields.get(
            "occurred_at",
            "",
        ),
    )
