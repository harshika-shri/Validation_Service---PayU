from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.control.agents.invoice_number_utils import (
    is_generated_invoice_number,
)
from src.control.validation_flow import (
    preserve_flow_outcome_state,
    should_continue_validation,
)
from src.data.models.postgres.enums import (
    IssueType,
    ValidationFlowOutcome,
    ValidationIssueStatus,
)
from src.data.repositories.duplicate_detection_repository import (
    DuplicateDetectionRepository,
    DuplicateInvoiceRecord,
)
from src.data.repositories.invoice_extracted_vendor_repository import (
    InvoiceExtractedVendorRepository,
)
from src.data.repositories.validation_issue_repository import (
    ValidationIssueCreate,
    ValidationIssueRepository,
)
from src.utils.duplicate_detection_utils import (
    InvoiceBusinessContent,
    business_content_is_identical,
)

logger = logging.getLogger(__name__)

CHECK_STAGE = "duplicate_detection"

DUPLICATE_INVOICE_NUMBER = "DUPLICATE_INVOICE_NUMBER"
POTENTIAL_DUPLICATE_INVOICE = "POTENTIAL_DUPLICATE_INVOICE"


@dataclass(frozen=True, slots=True)
class PendingIssue:
    issue_code: str
    check_name: str
    field_name: str
    issue_type: IssueType
    expected_value: str | None
    actual_value: str | None
    description: str


class DuplicateDetectionAgent:
    def __init__(
        self,
        duplicate_repo: DuplicateDetectionRepository,
        extracted_vendor_repo: InvoiceExtractedVendorRepository,
        validation_issue_repo: ValidationIssueRepository,
    ) -> None:
        self._duplicate_repo = duplicate_repo
        self._extracted_vendor_repo = extracted_vendor_repo
        self._validation_issue_repo = validation_issue_repo

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
                ValidationFlowOutcome.CONTINUE.value,
            ),
        )

        logger.info(
            "Starting duplicate detection",
            extra={
                "invoice_id": str(invoice_id),
                "flow_outcome": flow_outcome,
            },
        )

        if not should_continue_validation(
            state,
        ):
            logger.info(
                "Skipping duplicate detection due to flow stop",
                extra={
                    "invoice_id": str(invoice_id),
                    "flow_outcome": flow_outcome,
                },
            )
            return preserve_flow_outcome_state(
                invoice_id=invoice_id,
                po_id=state.get("po_id"),
                issue_codes=issue_codes,
                flow_outcome=flow_outcome,
            )

        current_invoice = await self._duplicate_repo.get_invoice_by_id(
            invoice_id,
        )

        if current_invoice is None:
            return preserve_flow_outcome_state(
                invoice_id=invoice_id,
                po_id=state.get("po_id"),
                issue_codes=issue_codes,
                flow_outcome=flow_outcome,
            )

        vendor_id = await self._resolve_vendor_id(
            invoice=current_invoice,
            invoice_id=invoice_id,
        )

        if vendor_id is None:
            logger.info(
                "Skipping duplicate detection; vendor unresolved",
                extra={
                    "invoice_id": str(invoice_id),
                },
            )
            return preserve_flow_outcome_state(
                invoice_id=invoice_id,
                po_id=state.get("po_id"),
                issue_codes=issue_codes,
                flow_outcome=flow_outcome,
            )

        current_content = (
            await self._duplicate_repo.get_business_content(
                invoice_id,
            )
        )

        pending_issues: list[PendingIssue] = []
        compared_invoice_ids: set[UUID] = set()
        invoice_number_matched = False

        if (
            not is_generated_invoice_number(
                current_invoice.invoice_number,
            )
            and current_invoice.invoice_number
        ):
            number_matches = (
                await self._duplicate_repo.find_by_vendor_and_invoice_number(
                    vendor_id=vendor_id,
                    invoice_number=current_invoice.invoice_number,
                    exclude_invoice_id=invoice_id,
                )
            )

            if number_matches:
                invoice_number_matched = True

            for candidate in number_matches:
                compared_invoice_ids.add(
                    candidate.id,
                )
                pending_issues.extend(
                    await self._compare_with_candidate(
                        current_invoice=current_invoice,
                        current_content=current_content,
                        candidate=candidate,
                        identical_issue_code=POTENTIAL_DUPLICATE_INVOICE,
                        different_issue_code=DUPLICATE_INVOICE_NUMBER,
                        check_name="invoice_number_reuse",
                    ),
                )

        if (
            is_generated_invoice_number(
                current_invoice.invoice_number,
            )
            or not invoice_number_matched
        ):
            pending_issues.extend(
                await self._detect_potential_duplicates(
                    invoice_id=invoice_id,
                    current_invoice=current_invoice,
                    current_content=current_content,
                    vendor_id=vendor_id,
                    exclude_invoice_ids=compared_invoice_ids,
                ),
            )

        issue_codes = await self._persist_issues(
            invoice_id=invoice_id,
            pending_issues=pending_issues,
            issue_codes=issue_codes,
        )

        logger.info(
            "Completed duplicate detection",
            extra={
                "invoice_id": str(invoice_id),
                "issue_count": len(pending_issues),
                "issue_codes": issue_codes,
            },
        )

        return preserve_flow_outcome_state(
            invoice_id=invoice_id,
            po_id=state.get("po_id"),
            issue_codes=issue_codes,
            flow_outcome=flow_outcome,
        )

    async def _resolve_vendor_id(
        self,
        invoice: DuplicateInvoiceRecord,
        invoice_id: UUID,
    ) -> UUID | None:
        if invoice.vendor_id is not None:
            return invoice.vendor_id

        extracted_vendor = (
            await self._extracted_vendor_repo.get_by_invoice_id(
                invoice_id,
            )
        )

        if extracted_vendor is None:
            return None

        return extracted_vendor.vendor_master_id

    async def _detect_potential_duplicates(
        self,
        invoice_id: UUID,
        current_invoice: DuplicateInvoiceRecord,
        current_content: InvoiceBusinessContent,
        vendor_id: UUID,
        exclude_invoice_ids: set[UUID],
    ) -> list[PendingIssue]:
        issues: list[PendingIssue] = []
        candidates = await self._duplicate_repo.find_by_vendor_id(
            vendor_id=vendor_id,
            exclude_invoice_id=invoice_id,
        )

        for candidate in candidates:
            if candidate.id in exclude_invoice_ids:
                continue

            candidate_issues = await self._compare_with_candidate(
                current_invoice=current_invoice,
                current_content=current_content,
                candidate=candidate,
                identical_issue_code=POTENTIAL_DUPLICATE_INVOICE,
                different_issue_code=POTENTIAL_DUPLICATE_INVOICE,
                check_name="potential_duplicate_detection",
                only_report_identical=True,
            )
            issues.extend(
                candidate_issues,
            )

        return issues

    async def _compare_with_candidate(
        self,
        current_invoice: DuplicateInvoiceRecord,
        current_content: InvoiceBusinessContent,
        candidate: DuplicateInvoiceRecord,
        identical_issue_code: str,
        different_issue_code: str,
        check_name: str,
        *,
        only_report_identical: bool = False,
    ) -> list[PendingIssue]:
        candidate_content = (
            await self._duplicate_repo.get_business_content(
                candidate.id,
            )
        )

        if business_content_is_identical(
            current_content,
            candidate_content,
        ):
            return [
                PendingIssue(
                    issue_code=identical_issue_code,
                    check_name=check_name,
                    field_name="invoice_id",
                    issue_type=IssueType.DUPLICATE,
                    expected_value=str(
                        candidate.id,
                    ),
                    actual_value=str(
                        current_invoice.id,
                    ),
                    description=(
                        "Invoice appears materially identical to "
                        f"previously submitted invoice "
                        f"{candidate.id}."
                    ),
                ),
            ]

        if only_report_identical:
            return []

        return [
            PendingIssue(
                issue_code=different_issue_code,
                check_name=check_name,
                field_name="invoice_number",
                issue_type=IssueType.DUPLICATE,
                expected_value=candidate.invoice_number,
                actual_value=current_invoice.invoice_number,
                description=(
                    "Invoice number already exists for this vendor "
                    "but business content differs from invoice "
                    f"{candidate.id}."
                ),
            ),
        ]

    async def _persist_issues(
        self,
        invoice_id: UUID,
        pending_issues: list[PendingIssue],
        issue_codes: list[str],
    ) -> list[str]:
        updated_codes = list(
            issue_codes,
        )

        for pending_issue in pending_issues:
            await self._validation_issue_repo.create_issue(
                invoice_id=invoice_id,
                issue=ValidationIssueCreate(
                    check_stage=CHECK_STAGE,
                    check_name=pending_issue.check_name,
                    field_name=pending_issue.field_name,
                    issue_type=pending_issue.issue_type,
                    issue_code=pending_issue.issue_code,
                    expected_value=pending_issue.expected_value,
                    actual_value=pending_issue.actual_value,
                    description=pending_issue.description,
                    status=ValidationIssueStatus.OPEN,
                ),
            )

            if pending_issue.issue_code not in updated_codes:
                updated_codes.append(
                    pending_issue.issue_code,
                )

        return updated_codes
