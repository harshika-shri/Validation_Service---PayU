from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from src.control.agents.po_resolution.line_allocation_search import (
    AllocationRecord,
    find_all_allocation_plans,
)
from src.control.agents.po_resolution.po_line_matcher import (
    POLineMatcher,
)
from src.control.validation_flow import (
    LINE_ITEM_VENDOR_CONFLICT,
    PO_MISSING,
    PO_UNRESOLVED,
    build_validation_state,
    should_continue_validation,
)
from src.data.models.postgres.enums import (
    IssueType,
    POResolutionCandidateType,
    ValidationIssueStatus,
)
from src.data.repositories.po_resolution.invoice_line_allocation_candidate_repository import (
    AllocationCandidateGroupCreate,
    AllocationCandidateItemCreate,
    InvoiceLineAllocationCandidateRepository,
)
from src.data.repositories.po_resolution.invoice_po_resolution_group_repository import (
    InvoicePOResolutionGroupRepository,
)
from src.data.repositories.line_item_validation.invoice_line_item_repository import (
    InvoiceLineItemRecord,
    InvoiceLineItemRepository,
)
from src.data.repositories.vendor_resolution.invoice_extracted_vendor_repository import (
    InvoiceExtractedVendorRepository,
)
from src.data.repositories.po_resolution.po_line_item_repository import (
    POLineItemRecord,
    POLineItemRepository,
)
from src.data.repositories.po_resolution.po_line_quantity_repository import (
    POLineQuantityRepository,
)
from src.data.repositories.po_resolution.purchase_order_repository import (
    PurchaseOrderRecord,
    PurchaseOrderRepository,
)
from src.data.repositories.shared.validation_issue_repository import (
    ValidationIssueCreate,
    ValidationIssueRepository,
)
from src.utils.po_line_matching_utils import (
    normalize_item_code,
    normalize_item_description,
)
from src.utils.po_candidate_description import (
    build_po_issue_context,
    enrich_pending_issues_with_po_context,
)

logger = logging.getLogger(__name__)

CHECK_STAGE = "line_item_validation"

DUPLICATE_INVOICE_LINE = "DUPLICATE_INVOICE_LINE"
MISSING_PO_COVERAGE = "MISSING_PO_COVERAGE"
UNMATCHED_LINE_ITEM = "UNMATCHED_LINE_ITEM"
AMBIGUOUS_LINE_MATCH = "AMBIGUOUS_LINE_MATCH"
QUANTITY_EXCEEDS_ORDERED = "QUANTITY_EXCEEDS_ORDERED"
QUANTITY_EXCEEDS_REMAINING = "QUANTITY_EXCEEDS_REMAINING"
INVALID_ALLOCATION = "INVALID_ALLOCATION"

_BLOCKING_ALLOCATION_ISSUE_CODES = frozenset(
    {
        PO_MISSING,
        PO_UNRESOLVED,
        UNMATCHED_LINE_ITEM,
        AMBIGUOUS_LINE_MATCH,
        LINE_ITEM_VENDOR_CONFLICT,
        MISSING_PO_COVERAGE,
    },
)


@dataclass(frozen=True, slots=True)
class PendingIssue:
    issue_code: str
    check_name: str
    field_name: str
    issue_type: IssueType
    expected_value: str | None
    actual_value: str | None
    description: str


class LineItemValidationAgent:
    def __init__(
        self,
        invoice_line_item_repo: InvoiceLineItemRepository,
        resolution_group_repo: InvoicePOResolutionGroupRepository,
        allocation_candidate_repo: InvoiceLineAllocationCandidateRepository,
        po_line_item_repo: POLineItemRepository,
        po_line_quantity_repo: POLineQuantityRepository,
        extracted_vendor_repo: InvoiceExtractedVendorRepository,
        purchase_order_repo: PurchaseOrderRepository,
        validation_issue_repo: ValidationIssueRepository,
    ) -> None:
        self._invoice_line_item_repo = invoice_line_item_repo
        self._resolution_group_repo = resolution_group_repo
        self._allocation_candidate_repo = allocation_candidate_repo
        self._po_line_item_repo = po_line_item_repo
        self._po_line_quantity_repo = po_line_quantity_repo
        self._extracted_vendor_repo = extracted_vendor_repo
        self._purchase_order_repo = purchase_order_repo
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

        logger.info(
            "Starting line item validation",
            extra={
                "invoice_id": str(invoice_id),
            },
        )

        if not should_continue_validation(
            state,
        ):
            logger.info(
                "Skipping line item validation due to flow stop",
                extra={
                    "invoice_id": str(invoice_id),
                    "flow_outcome": state.get(
                        "flow_outcome",
                    ),
                    "issue_codes": issue_codes,
                },
            )
            return build_validation_state(
                invoice_id=invoice_id,
                po_id=state.get("po_id"),
                issue_codes=issue_codes,
            )

        resolved_po_ids = (
            await self._resolution_group_repo.get_candidate_po_ids_for_validation(
                invoice_id,
            )
        )

        if not resolved_po_ids:
            logger.info(
                "Skipping line item validation; no candidate PO "
                "resolution group found",
                extra={
                    "invoice_id": str(invoice_id),
                },
            )
            return build_validation_state(
                invoice_id=invoice_id,
                po_id=state.get("po_id"),
                issue_codes=issue_codes,
            )

        invoice_lines = (
            await self._invoice_line_item_repo.get_by_invoice_id(
                invoice_id,
            )
        )

        pending_issues: list[PendingIssue] = []
        pending_issues.extend(
            self._detect_duplicate_lines(
                invoice_lines=invoice_lines,
            ),
        )

        if not invoice_lines:
            issue_codes = await self._persist_issues(
                invoice_id=invoice_id,
                pending_issues=pending_issues,
                issue_codes=issue_codes,
            )
            return build_validation_state(
                invoice_id=invoice_id,
                po_id=state.get("po_id"),
                issue_codes=issue_codes,
            )

        po_lines = await self._po_line_item_repo.get_by_po_ids(
            resolved_po_ids,
        )
        resolved_purchase_orders = (
            await self._purchase_order_repo.get_by_ids(
                resolved_po_ids,
            )
        )

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
            for line in uncovered_lines:
                pending_issues.append(
                    PendingIssue(
                        issue_code=MISSING_PO_COVERAGE,
                        check_name="coverage_validation",
                        field_name="item_description",
                        issue_type=IssueType.MISSING,
                        expected_value=None,
                        actual_value=line.item_description,
                        description=(
                            "Invoice line has no matching PO line "
                            "coverage in resolved purchase orders."
                        ),
                    ),
                )

            pending_issues = self._attach_resolved_po_context(
                pending_issues=pending_issues,
                purchase_orders=resolved_purchase_orders,
                po_lines=po_lines,
            )
            issue_codes = await self._persist_issues(
                invoice_id=invoice_id,
                pending_issues=pending_issues,
                issue_codes=issue_codes,
            )
            return build_validation_state(
                invoice_id=invoice_id,
                po_id=None,
                issue_codes=issue_codes,
            )

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
        po_line_by_id = {
            po_line.id: po_line
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

        if not allocation_plans:
            pending_issues.append(
                PendingIssue(
                    issue_code=UNMATCHED_LINE_ITEM,
                    check_name="allocation_search",
                    field_name="invoice_line_item_id",
                    issue_type=IssueType.MISSING,
                    expected_value=None,
                    actual_value=None,
                    description=(
                        "No valid allocation plan could be generated "
                        "for invoice line items."
                    ),
                ),
            )
            pending_issues = self._attach_resolved_po_context(
                pending_issues=pending_issues,
                purchase_orders=resolved_purchase_orders,
                po_lines=po_lines,
                available_quantity_by_line_id=po_line_capacity,
            )
            issue_codes = await self._persist_issues(
                invoice_id=invoice_id,
                pending_issues=pending_issues,
                issue_codes=issue_codes,
            )
            return build_validation_state(
                invoice_id=invoice_id,
                po_id=None,
                issue_codes=issue_codes,
            )

        if len(allocation_plans) > 1:
            pending_issues.append(
                PendingIssue(
                    issue_code=AMBIGUOUS_LINE_MATCH,
                    check_name="allocation_search",
                    field_name="invoice_line_item_id",
                    issue_type=IssueType.AMBIGUOUS,
                    expected_value=None,
                    actual_value=None,
                    description=(
                        "Multiple valid allocation plans were found "
                        "for invoice line items."
                    ),
                ),
            )
            pending_issues = self._attach_resolved_po_context(
                pending_issues=pending_issues,
                purchase_orders=resolved_purchase_orders,
                po_lines=po_lines,
                available_quantity_by_line_id=po_line_capacity,
                allocation_plans=allocation_plans,
            )
            issue_codes = await self._persist_issues(
                invoice_id=invoice_id,
                pending_issues=pending_issues,
                issue_codes=issue_codes,
            )
            await self._persist_allocation_candidates(
                invoice_id=invoice_id,
                plans=list(
                    allocation_plans,
                ),
                invoice_lines=invoice_lines,
                candidate_type=POResolutionCandidateType.AMBIGUOUS,
            )
            return build_validation_state(
                invoice_id=invoice_id,
                po_id=None,
                issue_codes=issue_codes,
            )

        resolved_plan = next(
            iter(allocation_plans),
        )

        quantity_by_line = {
            line.id: line.quantity_billed
            for line in invoice_lines
        }

        pending_issues.extend(
            self._validate_quantities(
                plan=resolved_plan,
                po_line_by_id=po_line_by_id,
                available_by_po_line=po_line_capacity,
            ),
        )
        pending_issues.extend(
            self._validate_allocation_consistency(
                plan=resolved_plan,
                quantity_by_line=quantity_by_line,
            ),
        )

        vendor_conflict = await self._validate_line_item_vendor_consistency(
            invoice_id=invoice_id,
            resolved_plan=resolved_plan,
        )

        if vendor_conflict is not None:
            pending_issues.append(
                vendor_conflict,
            )
            pending_issues = self._attach_resolved_po_context(
                pending_issues=pending_issues,
                purchase_orders=resolved_purchase_orders,
                po_lines=po_lines,
                available_quantity_by_line_id=po_line_capacity,
            )
            issue_codes = await self._persist_issues(
                invoice_id=invoice_id,
                pending_issues=pending_issues,
                issue_codes=issue_codes,
            )
            return build_validation_state(
                invoice_id=invoice_id,
                po_id=None,
                issue_codes=issue_codes,
            )

        open_issue_codes = set(
            await self._validation_issue_repo.get_open_issue_codes(
                invoice_id,
            ),
        )
        prior_blocking_issues = open_issue_codes.union(
            set(
                issue_codes,
            ),
        ).intersection(
            _BLOCKING_ALLOCATION_ISSUE_CODES,
        )

        if pending_issues or prior_blocking_issues:
            pending_issues = self._attach_resolved_po_context(
                pending_issues=pending_issues,
                purchase_orders=resolved_purchase_orders,
                po_lines=po_lines,
                available_quantity_by_line_id=po_line_capacity,
            )
            issue_codes = await self._persist_issues(
                invoice_id=invoice_id,
                pending_issues=pending_issues,
                issue_codes=issue_codes,
            )
            return build_validation_state(
                invoice_id=invoice_id,
                po_id=None,
                issue_codes=issue_codes,
            )

        resolution_groups = (
            await self._resolution_group_repo.get_groups_for_invoice(
                invoice_id,
            )
        )
        resolution_group_id = (
            resolution_groups[0].id
            if len(resolution_groups) == 1
            else None
        )
        allocation_candidate_type = (
            resolution_groups[0].candidate_type
            if len(resolution_groups) == 1
            else POResolutionCandidateType.RESOLVED
        )

        await self._persist_allocation_candidates(
            invoice_id=invoice_id,
            plans=[resolved_plan],
            invoice_lines=invoice_lines,
            candidate_type=allocation_candidate_type,
            resolution_group_id=resolution_group_id,
        )

        issue_codes = await self._persist_issues(
            invoice_id=invoice_id,
            pending_issues=pending_issues,
            issue_codes=issue_codes,
        )

        logger.info(
            "Completed line item validation",
            extra={
                "invoice_id": str(invoice_id),
                "validated_allocation_count": len(resolved_plan),
                "issue_codes": issue_codes,
            },
        )

        return build_validation_state(
            invoice_id=invoice_id,
            po_id=state.get("po_id"),
            issue_codes=issue_codes,
        )

    async def _validate_line_item_vendor_consistency(
        self,
        invoice_id: UUID,
        resolved_plan: tuple[AllocationRecord, ...],
    ) -> PendingIssue | None:
        extracted_vendor = (
            await self._extracted_vendor_repo.get_by_invoice_id(
                invoice_id,
            )
        )

        vendor_master_id = (
            extracted_vendor.vendor_master_id
            if extracted_vendor is not None
            else None
        )

        if vendor_master_id is None:
            return None

        po_ids = {
            record.po_id
            for record in resolved_plan
        }
        purchase_orders = (
            await self._purchase_order_repo.get_by_ids(
                list(
                    po_ids,
                ),
            )
        )

        for purchase_order in purchase_orders:
            if purchase_order.vendor_id != vendor_master_id:
                return PendingIssue(
                    issue_code=LINE_ITEM_VENDOR_CONFLICT,
                    check_name="line_item_vendor_consistency",
                    field_name="vendor_id",
                    issue_type=IssueType.MISMATCH,
                    expected_value=str(
                        vendor_master_id,
                    ),
                    actual_value=(
                        str(
                            purchase_order.vendor_id,
                        )
                        if purchase_order.vendor_id is not None
                        else None
                    ),
                    description=(
                        f"Matched PO {purchase_order.po_number} "
                        "belongs to a different vendor than the "
                        "resolved invoice vendor."
                    ),
                )

        return None

    @staticmethod
    def _detect_duplicate_lines(
        invoice_lines: list[InvoiceLineItemRecord],
    ) -> list[PendingIssue]:
        fingerprints = [
            LineItemValidationAgent._line_fingerprint(
                line,
            )
            for line in invoice_lines
        ]
        counts = Counter(
            fingerprints,
        )
        issues: list[PendingIssue] = []

        seen: set[tuple[str, str, Decimal, Decimal]] = set()

        for line, fingerprint in zip(
            invoice_lines,
            fingerprints,
            strict=True,
        ):
            if counts[fingerprint] <= 1:
                continue

            if fingerprint in seen:
                issues.append(
                    PendingIssue(
                        issue_code=DUPLICATE_INVOICE_LINE,
                        check_name="duplicate_detection",
                        field_name="line_number",
                        issue_type=IssueType.DUPLICATE,
                        expected_value=None,
                        actual_value=str(
                            line.line_number,
                        ),
                        description=(
                            "Duplicate invoice line detected with "
                            "matching item code, description, "
                            "quantity, and unit price."
                        ),
                    ),
                )
                continue

            seen.add(
                fingerprint,
            )

        return issues

    @staticmethod
    def _line_fingerprint(
        line: InvoiceLineItemRecord,
    ) -> tuple[str, str, Decimal, Decimal]:
        return (
            normalize_item_code(
                line.item_code or "",
            ),
            normalize_item_description(
                line.item_description or "",
            ),
            line.quantity_billed,
            line.unit_price,
        )

    @staticmethod
    def _validate_quantities(
        plan: tuple[AllocationRecord, ...],
        po_line_by_id: dict[UUID, POLineItemRecord],
        available_by_po_line: dict[UUID, Decimal],
    ) -> list[PendingIssue]:
        issues: list[PendingIssue] = []

        for record in plan:
            po_line = po_line_by_id.get(
                record.po_line_item_id,
            )

            if po_line is None:
                continue

            if record.allocated_quantity > po_line.quantity_ordered:
                issues.append(
                    PendingIssue(
                        issue_code=QUANTITY_EXCEEDS_ORDERED,
                        check_name="quantity_validation",
                        field_name="quantity_billed",
                        issue_type=IssueType.MISMATCH,
                        expected_value=str(
                            po_line.quantity_ordered,
                        ),
                        actual_value=str(
                            record.allocated_quantity,
                        ),
                        description=(
                            "Allocated quantity exceeds PO line "
                            "ordered quantity."
                        ),
                    ),
                )

            remaining = available_by_po_line.get(
                record.po_line_item_id,
                Decimal(0),
            )

            if record.allocated_quantity > remaining:
                issues.append(
                    PendingIssue(
                        issue_code=QUANTITY_EXCEEDS_REMAINING,
                        check_name="remaining_quantity_validation",
                        field_name="quantity_billed",
                        issue_type=IssueType.MISMATCH,
                        expected_value=str(
                            remaining,
                        ),
                        actual_value=str(
                            record.allocated_quantity,
                        ),
                        description=(
                            "Allocated quantity exceeds remaining "
                            "PO line quantity."
                        ),
                    ),
                )

        return issues

    @staticmethod
    def _validate_allocation_consistency(
        plan: tuple[AllocationRecord, ...],
        quantity_by_line: dict[UUID, Decimal],
    ) -> list[PendingIssue]:
        issues: list[PendingIssue] = []
        allocated_by_line: dict[UUID, Decimal] = {}

        for record in plan:
            allocated_by_line[
                record.invoice_line_item_id
            ] = allocated_by_line.get(
                record.invoice_line_item_id,
                Decimal(0),
            ) + record.allocated_quantity

        for invoice_line_id, invoice_quantity in (
            quantity_by_line.items()
        ):
            allocated_total = allocated_by_line.get(
                invoice_line_id,
                Decimal(0),
            )

            if allocated_total != invoice_quantity:
                issues.append(
                    PendingIssue(
                        issue_code=INVALID_ALLOCATION,
                        check_name="allocation_consistency",
                        field_name="quantity_billed",
                        issue_type=IssueType.INVALID,
                        expected_value=str(
                            invoice_quantity,
                        ),
                        actual_value=str(
                            allocated_total,
                        ),
                        description=(
                            "Sum of allocated quantities does not "
                            "equal invoice line quantity."
                        ),
                    ),
                )

        return issues

    @staticmethod
    def _attach_resolved_po_context(
        pending_issues: list[PendingIssue],
        purchase_orders: list[PurchaseOrderRecord],
        po_lines: list[POLineItemRecord],
        *,
        available_quantity_by_line_id: dict[UUID, Decimal] | None = None,
        allocation_plans: set[tuple[AllocationRecord, ...]] | None = None,
    ) -> list[PendingIssue]:
        context = build_po_issue_context(
            purchase_orders=purchase_orders,
            po_lines=po_lines,
            available_quantity_by_line_id=(
                available_quantity_by_line_id
            ),
            allocation_plans=allocation_plans,
        )

        return enrich_pending_issues_with_po_context(
            pending_issues,
            context,
        )

    async def _persist_allocation_candidates(
        self,
        invoice_id: UUID,
        plans: list[tuple[AllocationRecord, ...]],
        invoice_lines: list[InvoiceLineItemRecord],
        candidate_type: POResolutionCandidateType,
        resolution_group_id: UUID | None = None,
    ) -> None:
        if resolution_group_id is None:
            resolution_groups = (
                await self._resolution_group_repo.get_groups_for_invoice(
                    invoice_id,
                )
            )
            if len(resolution_groups) == 1:
                resolution_group_id = resolution_groups[0].id

        unit_price_by_line = {
            line.id: line.unit_price
            for line in invoice_lines
        }

        groups: list[AllocationCandidateGroupCreate] = []

        for plan in plans:
            group_type = (
                candidate_type
                if len(plans) == 1
                else POResolutionCandidateType.AMBIGUOUS
            )
            items: list[AllocationCandidateItemCreate] = []

            for record in plan:
                unit_price = unit_price_by_line.get(
                    record.invoice_line_item_id,
                    Decimal(0),
                )
                allocated_amount = (
                    record.allocated_quantity * unit_price
                ).quantize(
                    Decimal("0.01"),
                )
                items.append(
                    AllocationCandidateItemCreate(
                        invoice_line_item_id=record.invoice_line_item_id,
                        po_line_item_id=record.po_line_item_id,
                        allocated_quantity=record.allocated_quantity,
                        allocated_amount=allocated_amount,
                        candidate_type=group_type,
                    ),
                )

            groups.append(
                AllocationCandidateGroupCreate(
                    resolution_group_id=resolution_group_id,
                    candidate_type=group_type,
                    items=items,
                ),
            )

        await self._allocation_candidate_repo.replace_groups_for_invoice(
            invoice_id=invoice_id,
            groups=groups,
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
                    status=ValidationIssueStatus.OPEN,
                ),
            )

            if pending_issue.issue_code not in updated_codes:
                updated_codes.append(
                    pending_issue.issue_code,
                )

        return updated_codes

