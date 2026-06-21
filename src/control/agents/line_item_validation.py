from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from src.control.agents.line_allocation_search import (
    AllocationRecord,
    find_all_allocation_plans,
)
from src.control.agents.po_line_matcher import (
    POLineMatcher,
)
from src.control.validation_flow import (
    LINE_ITEM_VENDOR_CONFLICT,
    PO_AMBIGUOUS,
    PO_NOT_FOUND,
    PO_UNRESOLVED,
    build_validation_state,
    should_continue_validation,
)
from src.data.models.postgres.enums import (
    IssueType,
    ValidationIssueStatus,
)
from src.data.repositories.invoice_extracted_vendor_repository import (
    InvoiceExtractedVendorRepository,
)
from src.data.repositories.invoice_line_item_repository import (
    InvoiceLineItemRecord,
    InvoiceLineItemRepository,
)
from src.data.repositories.invoice_line_po_allocation_repository import (
    AllocationCreate,
    InvoiceLinePOAllocationRepository,
)
from src.data.repositories.invoice_po_mapping_repository import (
    InvoicePOMappingRepository,
)
from src.data.repositories.po_line_item_repository import (
    POLineItemRecord,
    POLineItemRepository,
)
from src.data.repositories.po_line_quantity_repository import (
    POLineQuantityRepository,
)
from src.data.repositories.purchase_order_repository import (
    PurchaseOrderRecord,
    PurchaseOrderRepository,
)
from src.data.repositories.validation_issue_repository import (
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
        PO_NOT_FOUND,
        PO_UNRESOLVED,
        PO_AMBIGUOUS,
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
        invoice_po_mapping_repo: InvoicePOMappingRepository,
        po_line_item_repo: POLineItemRepository,
        po_line_quantity_repo: POLineQuantityRepository,
        allocation_repo: InvoiceLinePOAllocationRepository,
        extracted_vendor_repo: InvoiceExtractedVendorRepository,
        purchase_order_repo: PurchaseOrderRepository,
        validation_issue_repo: ValidationIssueRepository,
    ) -> None:
        self._invoice_line_item_repo = invoice_line_item_repo
        self._invoice_po_mapping_repo = invoice_po_mapping_repo
        self._po_line_item_repo = po_line_item_repo
        self._po_line_quantity_repo = po_line_quantity_repo
        self._allocation_repo = allocation_repo
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
            await self._invoice_po_mapping_repo.get_po_ids_by_invoice_id(
                invoice_id,
            )
        )

        if not resolved_po_ids:
            logger.info(
                "Skipping line item validation; no resolved PO "
                "mappings found",
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
            await self._clear_po_resolution_artifacts(
                invoice_id,
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
            await self._clear_po_resolution_artifacts(
                invoice_id,
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
            await self._clear_po_resolution_artifacts(
                invoice_id,
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
            await self._clear_po_resolution_artifacts(
                invoice_id,
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
            await self._clear_po_resolution_artifacts(
                invoice_id,
            )
            return build_validation_state(
                invoice_id=invoice_id,
                po_id=None,
                issue_codes=issue_codes,
            )

        unit_price_by_line = {
            line.id: line.unit_price
            for line in invoice_lines
        }

        allocation_creates = [
            AllocationCreate(
                invoice_line_item_id=record.invoice_line_item_id,
                po_id=record.po_id,
                po_line_item_id=record.po_line_item_id,
                allocated_quantity=record.allocated_quantity,
                allocated_amount=(
                    record.allocated_quantity
                    * unit_price_by_line[
                        record.invoice_line_item_id
                    ]
                ).quantize(
                    Decimal("0.01"),
                ),
                match_type=record.match_type,
            )
            for record in resolved_plan
        ]

        await self._allocation_repo.replace_pending_allocations_for_invoice(
            invoice_id=invoice_id,
            allocations=allocation_creates,
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
                "allocation_count": len(resolved_plan),
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

    async def _clear_po_resolution_artifacts(
        self,
        invoice_id: UUID,
    ) -> None:
        await self._invoice_po_mapping_repo.delete_mappings_for_invoice(
            invoice_id,
        )
        await self._allocation_repo.cancel_pending_for_invoice(
            invoice_id,
        )

        logger.info(
            "Cleared PO mappings and pending allocations",
            extra={
                "invoice_id": str(invoice_id),
            },
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

