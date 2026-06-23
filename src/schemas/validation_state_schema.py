from uuid import UUID

from pydantic import BaseModel, Field

from src.data.models.postgres.enums import (
    InvoiceValidationDecision,
    InvoiceValidationOutcome,
    ValidationFlowOutcome,
)


class ReviewSummarySchema(BaseModel):
    id: UUID
    decision: str
    executive_summary: str
    system_recoveries: list[str] = Field(default_factory=list)
    open_issues: list[str] = Field(default_factory=list)
    vendor_clarifications: list[str] = Field(default_factory=list)
    resolved_po_numbers: list[str] = Field(default_factory=list)


class ValidationStateSchema(BaseModel):
    invoice_id: UUID
    po_id: UUID | None = None
    issue_codes: list[str] = Field(default_factory=list)
    open_issue_codes: list[str] = Field(default_factory=list)
    flow_outcome: ValidationFlowOutcome = ValidationFlowOutcome.CONTINUE
    decision: InvoiceValidationDecision | None = None
    invoice_status: InvoiceValidationOutcome | None = None
    review_summary: ReviewSummarySchema | None = None
