from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from src.control.validation_flow import (
    preserve_flow_outcome_state,
)
from src.core.exceptions.llm_exc import LLMServiceError
from src.core.exceptions.validation_exc import InvoiceNotFoundError
from src.data.models.postgres.enums import (
    InvoiceValidationDecision,
    InvoiceValidationOutcome,
    ValidationIssueStatus,
)
from src.data.repositories.invoice_header_resolution.invoice_repository import (
    InvoiceRepository,
)
from src.data.repositories.po_resolution.invoice_po_resolution_group_repository import (
    InvoicePOResolutionGroupRepository,
)
from src.data.repositories.po_resolution.purchase_order_repository import (
    PurchaseOrderRepository,
)
from src.data.repositories.review_summary_generation.invoice_review_summary_repository import (
    InvoiceReviewSummaryRepository,
    ReviewSummaryUpsert,
)
from src.data.repositories.shared.validation_issue_repository import (
    InvoiceIssueDetailRecord,
    ValidationIssueRepository,
)
from src.utils.llm_client import (
    generate_review_executive_summary,
)
from src.utils.review_summary_language import (
    build_open_issue_messages,
    build_vendor_clarification_messages,
    deduplicate_messages,
    recovery_message_for_issue,
    waived_message_for_issue,
)

logger = logging.getLogger(__name__)

CHECK_STAGE = "review_summary_generation"

_DECISION_LABELS = {
    InvoiceValidationDecision.APPROVED_AND_READY_TO_PAY.value: (
        "APPROVED_AND_READY_TO_PAY"
    ),
    InvoiceValidationDecision.PARTIAL_APPROVE.value: "PARTIAL_APPROVE",
    InvoiceValidationDecision.REJECT.value: "REJECT",
}

_OUTCOME_LABELS = {
    InvoiceValidationOutcome.RESOLVED.value: "RESOLVED",
    InvoiceValidationOutcome.RECOVERED.value: "RECOVERED",
    InvoiceValidationOutcome.AMBIGUOUS.value: "AMBIGUOUS",
    InvoiceValidationOutcome.UNRESOLVED.value: "UNRESOLVED",
    InvoiceValidationOutcome.DUPLICATE.value: "DUPLICATE",
}


class ReviewSummaryGenerationAgent:
    def __init__(
        self,
        invoice_repo: InvoiceRepository,
        validation_issue_repo: ValidationIssueRepository,
        review_summary_repo: InvoiceReviewSummaryRepository,
        resolution_group_repo: InvoicePOResolutionGroupRepository,
        purchase_order_repo: PurchaseOrderRepository,
    ) -> None:
        self._invoice_repo = invoice_repo
        self._validation_issue_repo = validation_issue_repo
        self._review_summary_repo = review_summary_repo
        self._resolution_group_repo = resolution_group_repo
        self._purchase_order_repo = purchase_order_repo

    async def run(
        self,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        invoice_id = UUID(
            str(state["invoice_id"]),
        )
        issue_codes: list[str] = list(
            state.get(
                "issue_codes",
                [],
            ),
        )
        flow_outcome = str(
            state.get(
                "flow_outcome",
            ),
        )
        decision_value = str(
            state.get(
                "decision",
                InvoiceValidationDecision.APPROVED_AND_READY_TO_PAY.value,
            ),
        )
        validation_outcome_value = state.get(
            "invoice_status",
        )

        invoice = await self._invoice_repo.get_review_summary_invoice(
            invoice_id,
        )

        if invoice is None:
            raise InvoiceNotFoundError(
                invoice_id=invoice_id,
            )

        validation_outcome = invoice.validation_outcome

        if validation_outcome is None and validation_outcome_value is not None:
            validation_outcome = InvoiceValidationOutcome(
                str(
                    validation_outcome_value,
                ),
            )

        invoice_issues = (
            await self._validation_issue_repo.get_invoice_issue_details(
                invoice_id,
            )
        )
        resolved_po_numbers = (
            await self._get_resolved_po_numbers(
                invoice_id,
            )
        )

        system_recoveries = self._build_system_recoveries(
            invoice_issues=invoice_issues,
            resolved_po_numbers=resolved_po_numbers,
        )
        open_issues = self._build_open_issues(
            invoice_issues=invoice_issues,
            resolved_po_numbers=resolved_po_numbers,
        )
        vendor_clarifications = self._build_vendor_clarifications(
            invoice_issues=invoice_issues,
            resolved_po_numbers=resolved_po_numbers,
        )
        executive_summary = self._generate_executive_summary(
            validation_outcome=validation_outcome,
            decision=decision_value,
            invoice_number=invoice.invoice_number,
            vendor_name=invoice.vendor_name,
            resolved_po_numbers=resolved_po_numbers,
            system_recoveries=system_recoveries,
            open_issues=open_issues,
            vendor_clarifications=vendor_clarifications,
        )

        summary_record = await self._review_summary_repo.upsert(
            invoice_id=invoice_id,
            summary=ReviewSummaryUpsert(
                decision=decision_value,
                executive_summary=executive_summary,
                system_recoveries=system_recoveries,
                open_issues=open_issues,
                vendor_clarifications=vendor_clarifications,
                validation_steps=dict(
                    state.get(
                        "validation_steps",
                        {},
                    )
                    or {},
                ),
            ),
        )

        outcome_value = (
            validation_outcome.value
            if validation_outcome is not None
            else None
        )

        logger.info(
            "Completed review summary generation",
            extra={
                "invoice_id": str(invoice_id),
                "decision": decision_value,
                "validation_outcome": outcome_value,
                "recovery_count": len(system_recoveries),
                "open_issue_count": len(open_issues),
                "clarification_count": len(vendor_clarifications),
            },
        )

        return preserve_flow_outcome_state(
            invoice_id=invoice_id,
            po_id=state.get("po_id"),
            issue_codes=issue_codes,
            flow_outcome=flow_outcome,
        ) | {
            "open_issue_codes": state.get(
                "open_issue_codes",
                [],
            ),
            "decision": decision_value,
            "invoice_status": outcome_value,
            "review_summary": {
                "id": str(summary_record.id),
                "decision": _DECISION_LABELS.get(
                    decision_value,
                    decision_value.upper(),
                ),
                "validation_outcome": (
                    _OUTCOME_LABELS.get(
                        outcome_value,
                        outcome_value.upper()
                        if outcome_value is not None
                        else None,
                    )
                ),
                "executive_summary": executive_summary,
                "system_recoveries": system_recoveries,
                "open_issues": open_issues,
                "vendor_clarifications": vendor_clarifications,
                "resolved_po_numbers": resolved_po_numbers,
            },
        }

    async def _get_resolved_po_numbers(
        self,
        invoice_id: UUID,
    ) -> list[str]:
        po_ids = (
            await self._resolution_group_repo.get_candidate_po_ids_for_validation(
                invoice_id,
            )
        )

        if not po_ids:
            groups = (
                await self._resolution_group_repo.get_groups_for_invoice(
                    invoice_id,
                )
            )
            po_ids = [
                po_id
                for group in groups
                for po_id in group.po_ids
            ]

        if not po_ids:
            return []

        purchase_orders = await self._purchase_order_repo.get_by_ids(
            po_ids,
        )

        return [
            purchase_order.po_number
            for purchase_order in sorted(
                purchase_orders,
                key=lambda record: record.po_number,
            )
        ]

    @staticmethod
    def _build_system_recoveries(
        invoice_issues: list[InvoiceIssueDetailRecord],
        resolved_po_numbers: list[str],
    ) -> list[str]:
        messages = [
            recovery_message_for_issue(
                issue.issue_code,
                {
                    **(
                        issue.metadata or {}
                    ),
                    **(
                        {
                            "resolved_po_numbers": (
                                resolved_po_numbers
                            ),
                        }
                        if resolved_po_numbers
                        else {}
                    ),
                },
            )
            for issue in invoice_issues
            if issue.status == ValidationIssueStatus.RESOLVED
            and issue.issue_code
            in {
                "MISSING_INVOICE_NUMBER",
                "VENDOR_NOT_FOUND",
                "PO_MISSING",
                "PO_RECOVERED",
                "INVALID_PO_REFERENCE",
            }
        ]
        messages.extend(
            waived_message_for_issue(
                issue.issue_code,
            )
            for issue in invoice_issues
            if issue.status == ValidationIssueStatus.WAIVED
            and issue.issue_code
            in {
                "MISSING_INVOICE_NUMBER",
                "VENDOR_NOT_FOUND",
                "PO_MISSING",
                "PO_RECOVERED",
                "INVALID_PO_REFERENCE",
            }
        )

        return deduplicate_messages(
            messages,
        )

    @staticmethod
    def _build_open_issues(
        invoice_issues: list[InvoiceIssueDetailRecord],
        resolved_po_numbers: list[str],
    ) -> list[str]:
        open_issue_codes = [
            issue.issue_code
            for issue in invoice_issues
            if issue.status
            in (
                ValidationIssueStatus.OPEN,
                ValidationIssueStatus.PENDING_REVIEW,
            )
            and issue.issue_code is not None
        ]

        return build_open_issue_messages(
            open_issue_codes,
            resolved_po_numbers=resolved_po_numbers,
        )

    @staticmethod
    def _build_vendor_clarifications(
        invoice_issues: list[InvoiceIssueDetailRecord],
        resolved_po_numbers: list[str],
    ) -> list[str]:
        open_issue_codes = [
            issue.issue_code
            for issue in invoice_issues
            if issue.status
            in (
                ValidationIssueStatus.OPEN,
                ValidationIssueStatus.PENDING_REVIEW,
            )
            and issue.issue_code is not None
        ]

        return build_vendor_clarification_messages(
            open_issue_codes,
            resolved_po_numbers=resolved_po_numbers,
        )

    @staticmethod
    def _generate_executive_summary(
        *,
        validation_outcome: InvoiceValidationOutcome | None,
        decision: str,
        invoice_number: str | None,
        vendor_name: str | None,
        resolved_po_numbers: list[str],
        system_recoveries: list[str],
        open_issues: list[str],
        vendor_clarifications: list[str],
    ) -> str:
        if (
            validation_outcome == InvoiceValidationOutcome.RESOLVED
            and not open_issues
        ):
            return (
                ReviewSummaryGenerationAgent._build_clear_approved_summary(
                    invoice_number=invoice_number,
                    vendor_name=vendor_name,
                    resolved_po_numbers=resolved_po_numbers,
                    system_recoveries=system_recoveries,
                )
            )

        if validation_outcome == InvoiceValidationOutcome.RECOVERED:
            return (
                ReviewSummaryGenerationAgent._build_recovered_summary(
                    invoice_number=invoice_number,
                    vendor_name=vendor_name,
                    resolved_po_numbers=resolved_po_numbers,
                    system_recoveries=system_recoveries,
                    open_issues=open_issues,
                )
            )

        if validation_outcome == InvoiceValidationOutcome.AMBIGUOUS:
            return (
                ReviewSummaryGenerationAgent._build_ambiguous_summary(
                    invoice_number=invoice_number,
                    vendor_name=vendor_name,
                )
            )

        if validation_outcome == InvoiceValidationOutcome.UNRESOLVED:
            return (
                ReviewSummaryGenerationAgent._build_unresolved_summary(
                    invoice_number=invoice_number,
                    vendor_name=vendor_name,
                )
            )

        if validation_outcome == InvoiceValidationOutcome.DUPLICATE:
            return (
                ReviewSummaryGenerationAgent._build_duplicate_summary(
                    invoice_number=invoice_number,
                    vendor_name=vendor_name,
                )
            )

        payload = {
            "decision": _DECISION_LABELS.get(
                decision,
                decision.upper(),
            ),
            "validation_outcome": (
                validation_outcome.value.upper()
                if validation_outcome is not None
                else None
            ),
            "invoice_number": invoice_number,
            "vendor_name": vendor_name,
            "resolved_po_numbers": resolved_po_numbers,
            "system_recoveries": system_recoveries,
            "open_issues": open_issues,
            "vendor_clarifications": vendor_clarifications,
        }

        try:
            return generate_review_executive_summary(
                payload,
            )
        except LLMServiceError:
            logger.exception(
                "LLM executive summary generation failed; "
                "using deterministic fallback",
            )
            return ReviewSummaryGenerationAgent._fallback_executive_summary(
                validation_outcome=validation_outcome,
                decision=decision,
                invoice_number=invoice_number,
                vendor_name=vendor_name,
                resolved_po_numbers=resolved_po_numbers,
                system_recoveries=system_recoveries,
                open_issues=open_issues,
                vendor_clarifications=vendor_clarifications,
            )

    @staticmethod
    def _build_clear_approved_summary(
        *,
        invoice_number: str | None,
        vendor_name: str | None,
        resolved_po_numbers: list[str],
        system_recoveries: list[str],
    ) -> str:
        invoice_label = invoice_number or "This invoice"
        vendor_label = (
            f" from {vendor_name}"
            if vendor_name
            else ""
        )
        sentences = [
            (
                f"{invoice_label}{vendor_label} is approved and "
                "ready to pay."
            ),
        ]

        if system_recoveries:
            sentences.append(
                system_recoveries[0],
            )
        elif resolved_po_numbers:
            po_list = ", ".join(
                resolved_po_numbers,
            )
            sentences.append(
                f"The invoice is matched to purchase order(s): "
                f"{po_list}.",
            )

        sentences.append(
            "Validation outcome: RESOLVED.",
        )
        sentences.append(
            "No vendor clarification is required.",
        )

        return " ".join(
            sentences[:4],
        )

    @staticmethod
    def _build_recovered_summary(
        *,
        invoice_number: str | None,
        vendor_name: str | None,
        resolved_po_numbers: list[str],
        system_recoveries: list[str],
        open_issues: list[str],
    ) -> str:
        invoice_label = invoice_number or "This invoice"
        vendor_label = (
            f" from {vendor_name}"
            if vendor_name
            else ""
        )
        sentences = [
            (
                f"{invoice_label}{vendor_label} is partially "
                "approved."
            ),
            "Validation outcome: RECOVERED.",
        ]

        if system_recoveries:
            sentences.extend(
                system_recoveries[:3],
            )
        elif resolved_po_numbers:
            po_list = ", ".join(
                resolved_po_numbers,
            )
            sentences.append(
                f"Matched purchase order(s): {po_list}.",
            )

        if open_issues:
            sentences.append(
                "Open validation findings remain for review.",
            )

        return " ".join(
            sentences[:6],
        )

    @staticmethod
    def _build_ambiguous_summary(
        *,
        invoice_number: str | None,
        vendor_name: str | None,
    ) -> str:
        invoice_label = invoice_number or "This invoice"
        vendor_label = (
            f" from {vendor_name}"
            if vendor_name
            else ""
        )

        return (
            f"{invoice_label}{vendor_label} was rejected due to "
            "multiple valid candidate solutions requiring human "
            "selection. Validation outcome: AMBIGUOUS."
        )

    @staticmethod
    def _build_unresolved_summary(
        *,
        invoice_number: str | None,
        vendor_name: str | None,
    ) -> str:
        invoice_label = invoice_number or "This invoice"
        vendor_label = (
            f" from {vendor_name}"
            if vendor_name
            else ""
        )

        return (
            f"{invoice_label}{vendor_label} was rejected because "
            "required validation entities could not be resolved. "
            "Validation outcome: UNRESOLVED."
        )

    @staticmethod
    def _build_duplicate_summary(
        *,
        invoice_number: str | None,
        vendor_name: str | None,
    ) -> str:
        invoice_label = invoice_number or "This invoice"
        vendor_label = (
            f" from {vendor_name}"
            if vendor_name
            else ""
        )

        return (
            f"{invoice_label}{vendor_label} was rejected due to "
            "duplicate invoice detection. Validation outcome: "
            "DUPLICATE."
        )

    @staticmethod
    def _fallback_executive_summary(
        *,
        validation_outcome: InvoiceValidationOutcome | None,
        decision: str,
        invoice_number: str | None,
        vendor_name: str | None,
        resolved_po_numbers: list[str],
        system_recoveries: list[str],
        open_issues: list[str],
        vendor_clarifications: list[str],
    ) -> str:
        invoice_label = invoice_number or "This invoice"
        vendor_label = (
            f" from {vendor_name}"
            if vendor_name
            else ""
        )
        outcome_label = (
            _OUTCOME_LABELS.get(
                validation_outcome.value,
                validation_outcome.value.upper(),
            )
            if validation_outcome is not None
            else _DECISION_LABELS.get(
                decision,
                decision.upper(),
            )
        )

        sentences = [
            (
                f"{invoice_label}{vendor_label} validation outcome "
                f"is {outcome_label}."
            ),
        ]

        if system_recoveries:
            sentences.extend(
                system_recoveries[:2],
            )
        elif resolved_po_numbers:
            po_list = ", ".join(
                resolved_po_numbers,
            )
            sentences.append(
                f"Matched purchase order(s): {po_list}.",
            )

        if open_issues:
            sentences.append(
                "Open validation findings remain on this invoice.",
            )
        else:
            sentences.append(
                "No open validation findings remain.",
            )

        if vendor_clarifications:
            sentences.append(
                "Vendor clarification may be required.",
            )

        return " ".join(
            sentences[:5],
        )
