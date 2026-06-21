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
    ValidationIssueStatus,
)
from src.data.repositories.invoice_po_mapping_repository import (
    InvoicePOMappingRepository,
)
from src.data.repositories.invoice_repository import (
    InvoiceRepository,
)
from src.data.repositories.invoice_review_summary_repository import (
    InvoiceReviewSummaryRepository,
    ReviewSummaryUpsert,
)
from src.data.repositories.purchase_order_repository import (
    PurchaseOrderRepository,
)
from src.data.repositories.validation_issue_repository import (
    InvoiceIssueDetailRecord,
    ValidationIssueRepository,
)
from src.utils.llm_client import (
    generate_review_executive_summary,
)
from src.utils.review_summary_language import (
    clarification_topic_for_issue,
    deduplicate_messages,
    open_issue_message_for_issue,
    recovery_message_for_issue,
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


class ReviewSummaryGenerationAgent:
    def __init__(
        self,
        invoice_repo: InvoiceRepository,
        validation_issue_repo: ValidationIssueRepository,
        review_summary_repo: InvoiceReviewSummaryRepository,
        invoice_po_mapping_repo: InvoicePOMappingRepository,
        purchase_order_repo: PurchaseOrderRepository,
    ) -> None:
        self._invoice_repo = invoice_repo
        self._validation_issue_repo = validation_issue_repo
        self._review_summary_repo = review_summary_repo
        self._invoice_po_mapping_repo = invoice_po_mapping_repo
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

        invoice = await self._invoice_repo.get_review_summary_invoice(
            invoice_id,
        )

        if invoice is None:
            raise InvoiceNotFoundError(
                invoice_id=invoice_id,
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
        )
        vendor_clarifications = self._build_vendor_clarifications(
            invoice_issues=invoice_issues,
        )
        executive_summary = self._generate_executive_summary(
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
            ),
        )

        logger.info(
            "Completed review summary generation",
            extra={
                "invoice_id": str(invoice_id),
                "decision": decision_value,
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
            "invoice_status": state.get(
                "invoice_status",
            ),
            "review_summary": {
                "id": str(summary_record.id),
                "decision": _DECISION_LABELS.get(
                    decision_value,
                    decision_value.upper(),
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
            await self._invoice_po_mapping_repo.get_po_ids_by_invoice_id(
                invoice_id,
            )
        )

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
                "PO_NOT_FOUND",
                "INVALID_PO_REFERENCE",
            }
        ]

        return deduplicate_messages(
            messages,
        )

    @staticmethod
    def _build_open_issues(
        invoice_issues: list[InvoiceIssueDetailRecord],
    ) -> list[str]:
        messages = [
            open_issue_message_for_issue(
                issue.issue_code,
            )
            for issue in invoice_issues
            if issue.status == ValidationIssueStatus.OPEN
        ]

        return deduplicate_messages(
            messages,
        )

    @staticmethod
    def _build_vendor_clarifications(
        invoice_issues: list[InvoiceIssueDetailRecord],
    ) -> list[str]:
        topics: list[str] = []

        for issue in invoice_issues:
            if issue.status != ValidationIssueStatus.OPEN:
                continue

            topic = clarification_topic_for_issue(
                issue.issue_code,
            )

            if topic is None:
                continue

            topics.append(
                topic,
            )

        return deduplicate_messages(
            topics,
        )

    @staticmethod
    def _generate_executive_summary(
        decision: str,
        invoice_number: str | None,
        vendor_name: str | None,
        resolved_po_numbers: list[str],
        system_recoveries: list[str],
        open_issues: list[str],
        vendor_clarifications: list[str],
    ) -> str:
        if (
            decision
            == InvoiceValidationDecision.APPROVED_AND_READY_TO_PAY.value
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

        payload = {
            "decision": _DECISION_LABELS.get(
                decision,
                decision.upper(),
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
            "All validation checks passed and no unresolved findings "
            "remain.",
        )
        sentences.append(
            "No vendor clarification is required.",
        )

        return " ".join(
            sentences[:4],
        )

    @staticmethod
    def _fallback_executive_summary(
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
        decision_label = _DECISION_LABELS.get(
            decision,
            decision.upper(),
        )

        sentences = [
            (
                f"{invoice_label}{vendor_label} validation outcome is "
                f"{decision_label}."
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
                "Unresolved validation findings remain on this invoice.",
            )
        else:
            sentences.append(
                "No unresolved validation findings remain.",
            )

        if vendor_clarifications:
            sentences.append(
                "Vendor clarification is required before final approval.",
            )
        else:
            sentences.append(
                "No vendor clarification is required.",
            )

        return " ".join(
            sentences[:5],
        )
