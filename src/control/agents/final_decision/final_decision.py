from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from src.control.validation_flow import (
    preserve_flow_outcome_state,
)
from src.core.services.validation_outcome_service import (
    ValidationOutcomeService,
)
from src.data.models.postgres.enums import (
    InvoiceValidationDecision,
    InvoiceValidationOutcome,
    ValidationIssueStatus,
)
from src.data.repositories.invoice_header_resolution.invoice_repository import (
    InvoiceRepository,
)
from src.data.repositories.po_resolution.invoice_line_allocation_candidate_repository import (
    InvoiceLineAllocationCandidateRepository,
)
from src.data.repositories.shared.validation_issue_repository import (
    ValidationIssueRepository,
)

logger = logging.getLogger(__name__)

CHECK_STAGE = "final_decision"

_OUTCOME_TO_DECISION = {
    InvoiceValidationOutcome.RESOLVED: (
        InvoiceValidationDecision.APPROVED_AND_READY_TO_PAY
    ),
    InvoiceValidationOutcome.RECOVERED: (
        InvoiceValidationDecision.PARTIAL_APPROVE
    ),
    InvoiceValidationOutcome.AMBIGUOUS: (
        InvoiceValidationDecision.REJECT
    ),
    InvoiceValidationOutcome.UNRESOLVED: (
        InvoiceValidationDecision.REJECT
    ),
    InvoiceValidationOutcome.DUPLICATE: (
        InvoiceValidationDecision.REJECT
    ),
}


class FinalDecisionAgent:
    def __init__(
        self,
        validation_issue_repo: ValidationIssueRepository,
        invoice_repo: InvoiceRepository,
        validation_outcome_service: ValidationOutcomeService,
        allocation_candidate_repo: InvoiceLineAllocationCandidateRepository,
    ) -> None:
        self._validation_issue_repo = validation_issue_repo
        self._invoice_repo = invoice_repo
        self._validation_outcome_service = validation_outcome_service
        self._allocation_candidate_repo = allocation_candidate_repo

    async def run(
        self,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        invoice_id = UUID(
            str(state["invoice_id"]),
        )
        flow_outcome = str(
            state.get(
                "flow_outcome",
            ),
        )
        issue_codes: list[str] = list(
            state.get(
                "issue_codes",
                [],
            ),
        )

        validation_outcome = (
            await self._invoice_repo.get_validation_outcome(
                invoice_id,
            )
        )

        if validation_outcome is None:
            validation_outcome = (
                await self._validation_outcome_service.resolve_and_persist(
                    invoice_id=invoice_id,
                    issue_codes=issue_codes,
                )
            )

        decision = _OUTCOME_TO_DECISION[
            validation_outcome
        ]

        if decision == InvoiceValidationDecision.REJECT:
            await self._allocation_candidate_repo.delete_groups_for_invoice(
                invoice_id,
            )

        open_issue_codes = [
            issue.issue_code
            for issue in (
                await self._validation_issue_repo.get_invoice_issues(
                    invoice_id,
                )
            )
            if issue.status
            in (
                ValidationIssueStatus.OPEN,
                ValidationIssueStatus.PENDING_REVIEW,
            )
        ]

        logger.info(
            "Completed final decision",
            extra={
                "invoice_id": str(invoice_id),
                "decision": decision.value,
                "invoice_status": validation_outcome.value,
                "open_issue_codes": open_issue_codes,
            },
        )

        return preserve_flow_outcome_state(
            invoice_id=invoice_id,
            po_id=state.get("po_id"),
            issue_codes=open_issue_codes,
            flow_outcome=flow_outcome,
        ) | {
            "open_issue_codes": open_issue_codes,
            "decision": decision.value,
            "invoice_status": validation_outcome.value,
        }
