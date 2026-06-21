from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from src.core.services.allocation_lifecycle_service import (
    AllocationLifecycleService,
)
from src.control.validation_flow import (
    preserve_flow_outcome_state,
)
from src.data.models.postgres.enums import (
    InvoiceStatus,
    InvoiceValidationDecision,
    IssueDecisionCategory,
    ValidationIssueStatus,
)
from src.data.repositories.invoice_po_mapping_repository import (
    InvoicePOMappingRepository,
)
from src.data.repositories.invoice_repository import (
    InvoiceRepository,
)
from src.data.repositories.issue_decision_rules_repository import (
    IssueDecisionRulesRepository,
)
from src.data.repositories.validation_issue_repository import (
    InvoiceIssueRecord,
    ValidationIssueRepository,
)

logger = logging.getLogger(__name__)

CHECK_STAGE = "final_decision"

_DECISION_TO_INVOICE_STATUS = {
    InvoiceValidationDecision.APPROVED_AND_READY_TO_PAY: (
        InvoiceStatus.APPROVED_READY_TO_PAY
    ),
    InvoiceValidationDecision.PARTIAL_APPROVE: (
        InvoiceStatus.PENDING_ACTION
    ),
    InvoiceValidationDecision.REJECT: InvoiceStatus.MATCH_ISSUES,
}


class FinalDecisionAgent:
    def __init__(
        self,
        validation_issue_repo: ValidationIssueRepository,
        decision_rules_repo: IssueDecisionRulesRepository,
        invoice_repo: InvoiceRepository,
        invoice_po_mapping_repo: InvoicePOMappingRepository,
        allocation_lifecycle_service: AllocationLifecycleService,
    ) -> None:
        self._validation_issue_repo = validation_issue_repo
        self._decision_rules_repo = decision_rules_repo
        self._invoice_repo = invoice_repo
        self._invoice_po_mapping_repo = invoice_po_mapping_repo
        self._allocation_lifecycle_service = allocation_lifecycle_service

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

        invoice_issues = (
            await self._validation_issue_repo.get_invoice_issues(
                invoice_id,
            )
        )
        decision_rules = (
            await self._decision_rules_repo.get_all_decision_rules()
        )
        rules_by_code = {
            rule.issue_code: rule.decision_category
            for rule in decision_rules
        }

        decision = self._determine_decision(
            invoice_issues=invoice_issues,
            rules_by_code=rules_by_code,
        )
        invoice_status = _DECISION_TO_INVOICE_STATUS[
            decision
        ]

        await self._invoice_repo.update_invoice_status(
            invoice_id,
            invoice_status,
        )

        if decision == InvoiceValidationDecision.REJECT:
            await self._allocation_lifecycle_service.cancel_allocations(
                invoice_id,
            )
            await self._invoice_po_mapping_repo.delete_mappings_for_invoice(
                invoice_id,
            )

        open_issue_codes = [
            issue.issue_code
            for issue in invoice_issues
            if issue.status == ValidationIssueStatus.OPEN
        ]

        logger.info(
            "Completed final decision",
            extra={
                "invoice_id": str(invoice_id),
                "decision": decision.value,
                "invoice_status": invoice_status.value,
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
            "invoice_status": invoice_status.value,
        }

    @staticmethod
    def _determine_decision(
        invoice_issues: list[InvoiceIssueRecord],
        rules_by_code: dict[str, IssueDecisionCategory],
    ) -> InvoiceValidationDecision:
        open_issues = [
            issue
            for issue in invoice_issues
            if issue.status == ValidationIssueStatus.OPEN
        ]

        for issue in open_issues:
            category = FinalDecisionAgent._category_for_issue(
                issue_code=issue.issue_code,
                rules_by_code=rules_by_code,
            )

            if category == IssueDecisionCategory.REJECT:
                return InvoiceValidationDecision.REJECT

        for issue in open_issues:
            category = FinalDecisionAgent._category_for_issue(
                issue_code=issue.issue_code,
                rules_by_code=rules_by_code,
            )

            if category == IssueDecisionCategory.PARTIAL_APPROVE:
                return InvoiceValidationDecision.PARTIAL_APPROVE

        return InvoiceValidationDecision.APPROVED_AND_READY_TO_PAY

    @staticmethod
    def _category_for_issue(
        issue_code: str,
        rules_by_code: dict[str, IssueDecisionCategory],
    ) -> IssueDecisionCategory:
        return rules_by_code.get(
            issue_code,
            IssueDecisionCategory.PARTIAL_APPROVE,
        )
