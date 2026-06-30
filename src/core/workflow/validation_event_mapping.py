from __future__ import annotations

from src.constants.validation_event_constants import (
    VALIDATION_EVENT_TYPE_AMBIGUOUS,
    VALIDATION_EVENT_TYPE_DUPLICATE,
    VALIDATION_EVENT_TYPE_RECOVERED,
    VALIDATION_EVENT_TYPE_RESOLVED,
    VALIDATION_EVENT_TYPE_UNRESOLVED,
)
from src.data.models.postgres.enums import (
    InvoiceValidationOutcome,
)


def map_outcome_to_event_type(
    outcome: InvoiceValidationOutcome,
) -> str:
    return _OUTCOME_TO_EVENT_TYPE[outcome]


_OUTCOME_TO_EVENT_TYPE: dict[InvoiceValidationOutcome, str] = {
    InvoiceValidationOutcome.RESOLVED: VALIDATION_EVENT_TYPE_RESOLVED,
    InvoiceValidationOutcome.RECOVERED: VALIDATION_EVENT_TYPE_RECOVERED,
    InvoiceValidationOutcome.AMBIGUOUS: VALIDATION_EVENT_TYPE_AMBIGUOUS,
    InvoiceValidationOutcome.UNRESOLVED: VALIDATION_EVENT_TYPE_UNRESOLVED,
    InvoiceValidationOutcome.DUPLICATE: VALIDATION_EVENT_TYPE_DUPLICATE,
}
