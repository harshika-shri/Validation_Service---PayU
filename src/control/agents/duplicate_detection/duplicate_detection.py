from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.constants.validation_issue_codes import (
    DUPLICATE_INVOICE_NUMBER,
    POTENTIAL_DUPLICATE_INVOICE,
)
from src.control.agents.invoice_header_resolution.invoice_number_utils import (
    is_generated_invoice_number,
)
from src.control.agents.po_resolution.line_allocation_search import (
    find_all_allocation_plans,
)
from src.control.agents.po_resolution.po_line_matcher import (
    POLineMatcher,
)
from src.control.validation_flow import (
    preserve_flow_outcome_state,
    should_continue_validation,
)
from src.core.services.validation_outcome_service import (
    ValidationOutcomeService,
)
from src.data.models.postgres.enums import (
    IssueType,
    ValidationFlowOutcome,
    ValidationIssueStatus,
)
from src.data.repositories.duplicate_detection.duplicate_detection_repository import (
    DuplicateDetectionRepository,
    DuplicateInvoiceRecord,
)
from src.data.repositories.line_item_validation.invoice_line_item_repository import (
    InvoiceLineItemRepository,
)
from src.data.repositories.po_resolution.invoice_po_resolution_group_repository import (
    InvoicePOResolutionGroupRepository,
)
from src.data.repositories.po_resolution.po_line_item_repository import (
    POLineItemRepository,
)
from src.data.repositories.po_resolution.po_line_quantity_repository import (
    POLineQuantityRepository,
)
from src.data.repositories.shared.validation_issue_repository import (
    ValidationIssueCreate,
    ValidationIssueRepository,
)
from src.data.repositories.vendor_resolution.invoice_extracted_vendor_repository import (
    InvoiceExtractedVendorRepository,
)
from src.utils.duplicate_detection_utils import (
    InvoiceBusinessContent,
    business_content_is_identical,
)

logger = logging.getLogger(__name__)

CHECK_STAGE = "duplicate_detection"


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
        resolution_group_repo: InvoicePOResolutionGroupRepository,
        invoice_line_item_repo: InvoiceLineItemRepository,
        po_line_item_repo: POLineItemRepository,
        po_line_quantity_repo: POLineQuantityRepository,
        validation_outcome_service: ValidationOutcomeService,
        validation_issue_repo: ValidationIssueRepository,
    ) -> None:
        self._duplicate_repo = duplicate_repo
        self._extracted_vendor_repo = extracted_vendor_repo
        self._resolution_group_repo = resolution_group_repo
        self._invoice_line_item_repo = invoice_line_item_repo
        self._po_line_item_repo = po_line_item_repo
        self._po_line_quantity_repo = po_line_quantity_repo
        self._validation_outcome_service = validation_outcome_service
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

                pending_issues.append(
                    PendingIssue(
                        issue_code=DUPLICATE_INVOICE_NUMBER,
                        check_name="invoice_number_reuse",
                        field_name="invoice_number",
                        issue_type=IssueType.DUPLICATE,
                        expected_value=current_invoice.invoice_number,
                        actual_value=current_invoice.invoice_number,
                        description=(
                            "An invoice with the same vendor and "
                            "invoice number already exists in the "
                            "system."
                        ),
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

        await self._validation_outcome_service.resolve_and_persist(
            invoice_id=invoice_id,
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

            candidate_issue = await self._evaluate_potential_duplicate(
                invoice_id=invoice_id,
                current_invoice=current_invoice,
                current_content=current_content,
                candidate=candidate,
            )

            if candidate_issue is not None:
                issues.append(
                    candidate_issue,
                )

        return issues

    async def _evaluate_potential_duplicate(
        self,
        invoice_id: UUID,
        current_invoice: DuplicateInvoiceRecord,
        current_content: InvoiceBusinessContent,
        candidate: DuplicateInvoiceRecord,
    ) -> PendingIssue | None:
        candidate_content = (
            await self._duplicate_repo.get_business_content(
                candidate.id,
            )
        )

        if not business_content_is_identical(
            current_content,
            candidate_content,
        ):
            return None

        if await self._has_sufficient_po_availability(
            invoice_id,
        ):
            return None

        return PendingIssue(
            issue_code=POTENTIAL_DUPLICATE_INVOICE,
            check_name="potential_duplicate_detection",
            field_name="invoice_id",
            issue_type=IssueType.DUPLICATE,
            expected_value=str(
                candidate.id,
            ),
            actual_value=str(
                current_invoice.id,
            ),
            description=(
                "This invoice appears materially identical to a "
                "previously submitted invoice and may represent a "
                "duplicate submission."
            ),
        )

    async def _has_sufficient_po_availability(
        self,
        invoice_id: UUID,
    ) -> bool:
        po_ids = (
            await self._resolution_group_repo.get_candidate_po_ids_for_validation(
                invoice_id,
            )
        )

        if not po_ids:
            return False

        invoice_lines = (
            await self._invoice_line_item_repo.get_by_invoice_id(
                invoice_id,
            )
        )

        if not invoice_lines:
            return False

        po_lines = await self._po_line_item_repo.get_by_po_ids(
            po_ids,
        )

        if not po_lines:
            return False

        matcher = POLineMatcher()
        match_edges = await matcher.build_typed_match_edges(
            invoice_lines=invoice_lines,
            po_lines=po_lines,
        )

        uncovered_lines = [
            line
            for line in invoice_lines
            if not match_edges.get(
                line.id,
                [],
            )
        ]

        if uncovered_lines:
            return False

        quantity_ordered_by_id = {
            po_line.id: po_line.quantity_ordered
            for po_line in po_lines
        }
        po_line_capacity = (
            await self._po_line_quantity_repo.get_available_quantities(
                po_line_ids=[
                    po_line.id
                    for po_line in po_lines
                ],
                quantity_ordered_by_id=quantity_ordered_by_id,
                exclude_invoice_id=invoice_id,
            )
        )
        po_line_to_po = {
            po_line.id: po_line.po_id
            for po_line in po_lines
        }

        allocation_plans = find_all_allocation_plans(
            invoice_line_ids=[
                line.id
                for line in invoice_lines
            ],
            quantity_by_line={
                line.id: line.quantity_billed
                for line in invoice_lines
            },
            match_edges=match_edges,
            po_line_capacity=po_line_capacity,
            po_line_to_po=po_line_to_po,
        )

        return bool(
            allocation_plans,
        )

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
                    status=ValidationIssueStatus.PENDING_REVIEW,
                ),
            )

            if pending_issue.issue_code not in updated_codes:
                updated_codes.append(
                    pending_issue.issue_code,
                )

        return updated_codes
