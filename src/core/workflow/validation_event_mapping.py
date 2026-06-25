from __future__ import annotations

from dataclasses import dataclass

from src.constants.validation_event_constants import (
    VALIDATION_EVENT_TYPE_COMPLETED,
    VALIDATION_EVENT_TYPE_PENDING_REVIEW,
    VALIDATION_EVENT_TYPE_REJECTED,
)
from src.data.models.postgres.enums import (
    InvoiceValidationDecision,
    InvoiceValidationOutcome,
)


@dataclass(frozen=True, slots=True)
class ValidationWorkflowEvent:
    event_type: str
    validation_outcome: InvoiceValidationOutcome


_DECISION_TO_WORKFLOW_EVENT: dict[
    InvoiceValidationDecision,
    ValidationWorkflowEvent,
] = {
    InvoiceValidationDecision.APPROVED_AND_READY_TO_PAY: ValidationWorkflowEvent(
        event_type=VALIDATION_EVENT_TYPE_COMPLETED,
        validation_outcome=InvoiceValidationOutcome.APPROVED,
    ),
    InvoiceValidationDecision.PARTIAL_APPROVE: ValidationWorkflowEvent(
        event_type=VALIDATION_EVENT_TYPE_PENDING_REVIEW,
        validation_outcome=InvoiceValidationOutcome.PENDING_REVIEW,
    ),
    InvoiceValidationDecision.REJECT: ValidationWorkflowEvent(
        event_type=VALIDATION_EVENT_TYPE_REJECTED,
        validation_outcome=InvoiceValidationOutcome.REJECTED,
    ),
}


def map_decision_to_workflow_event(
    decision: InvoiceValidationDecision,
) -> ValidationWorkflowEvent:
    return _DECISION_TO_WORKFLOW_EVENT[decision]
