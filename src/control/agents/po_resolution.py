from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import date
from typing import Any
from uuid import UUID

from src.config.settings import settings
from src.control.agents.line_allocation_search import (
    find_all_allocation_plans,
)
from src.control.agents.po_coverage_search import (
    filter_pos_by_invoice_date,
)
from src.control.agents.po_line_matcher import (
    POLineMatcher,
)
from src.control.validation_flow import build_validation_state
from src.core.exceptions.validation_exc import InvoiceNotFoundError
from src.data.models.postgres.enums import (
    IssueType,
    PurchaseOrderStatus,
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
    InvoiceLinePOAllocationRepository,
)
from src.data.repositories.invoice_po_mapping_repository import (
    InvoicePOMappingRepository,
)
from src.data.repositories.invoice_po_resolution_repository import (
    InvoicePOResolutionRepository,
    POResolutionInvoiceRecord,
)
from src.data.repositories.po_line_item_repository import (
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
from src.utils.po_candidate_description import (
    append_po_context,
    build_candidate_pos_metadata,
    build_po_issue_context,
    enrich_pending_issues_with_po_context,
)

logger = logging.getLogger(__name__)

CHECK_STAGE = "po_resolution"

VENDOR_NOT_FOUND = "VENDOR_NOT_FOUND"
PO_NOT_FOUND = "PO_NOT_FOUND"
PO_CLOSED = "PO_CLOSED"
PO_UNRESOLVED = "PO_UNRESOLVED"
PO_AMBIGUOUS = "PO_AMBIGUOUS"
INVALID_PO_REFERENCE = "INVALID_PO_REFERENCE"
PO_VENDOR_CONFLICT = "PO_VENDOR_CONFLICT"

_RECOVERABLE_PO_ISSUE_CODES = frozenset(
    {
        PO_NOT_FOUND,
        INVALID_PO_REFERENCE,
    },
)

_ACTIVE_PO_STATUSES = (
    PurchaseOrderStatus.OPEN,
    PurchaseOrderStatus.PARTIALLY_PROCESSED,
)

_INVALID_PO_PLACEHOLDERS = frozenset(
    {
        "---",
        "-",
        "n/a",
        "na",
        "none",
        "null",
        "nil",
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
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class _ExtractedPOResult:
    matched_pos: list[PurchaseOrderRecord]
    pending_issues: tuple[PendingIssue, ...]


@dataclass(frozen=True, slots=True)
class _POSearchResult:
    po_sets: set[frozenset[UUID]]
    allocation_plan_count: int
    matching_po_ids: set[UUID]


class POResolutionAgent:
    def __init__(
        self,
        invoice_po_repo: InvoicePOResolutionRepository,
        invoice_line_item_repo: InvoiceLineItemRepository,
        extracted_vendor_repo: InvoiceExtractedVendorRepository,
        purchase_order_repo: PurchaseOrderRepository,
        po_line_item_repo: POLineItemRepository,
        po_line_quantity_repo: POLineQuantityRepository,
        invoice_po_mapping_repo: InvoicePOMappingRepository,
        allocation_repo: InvoiceLinePOAllocationRepository,
        validation_issue_repo: ValidationIssueRepository,
    ) -> None:
        self._invoice_po_repo = invoice_po_repo
        self._invoice_line_item_repo = invoice_line_item_repo
        self._extracted_vendor_repo = extracted_vendor_repo
        self._purchase_order_repo = purchase_order_repo
        self._po_line_item_repo = po_line_item_repo
        self._po_line_quantity_repo = po_line_quantity_repo
        self._invoice_po_mapping_repo = invoice_po_mapping_repo
        self._allocation_repo = allocation_repo
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
            "Starting PO resolution",
            extra={
                "invoice_id": str(invoice_id),
            },
        )

        invoice = await self._invoice_po_repo.get_po_resolution_invoice(
            invoice_id,
        )

        if invoice is None:
            raise InvoiceNotFoundError(
                invoice_id=invoice_id,
            )

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
            issue_codes = await self._persist_issues(
                invoice_id=invoice_id,
                pending_issues=[
                    PendingIssue(
                        issue_code=VENDOR_NOT_FOUND,
                        check_name="vendor_precondition",
                        field_name="vendor_master_id",
                        issue_type=IssueType.MISSING,
                        expected_value=None,
                        actual_value=None,
                        description=(
                            "Vendor is unresolved; PO resolution "
                            "cannot proceed."
                        ),
                    ),
                ],
                issue_codes=issue_codes,
            )
            return await self._return_po_resolution_failure(
                invoice_id=invoice_id,
                issue_codes=issue_codes,
            )

        pending_issues: list[PendingIssue] = []

        extracted_result = await self._validate_extracted_po_numbers(
            invoice=invoice,
        )
        pending_issues.extend(
            extracted_result.pending_issues,
        )

        invoice_lines = (
            await self._invoice_line_item_repo.get_by_invoice_id(
                invoice_id,
            )
        )

        po_reference_missing = (
            not invoice.po_numbers_extracted
        )

        direct_solution = (
            await self._try_direct_extracted_po_resolution(
                invoice_id=invoice_id,
                invoice_lines=invoice_lines,
                matched_pos=extracted_result.matched_pos,
            )
        )

        if direct_solution is not None:
            logger.info(
                "Resolved invoice using extracted PO reference",
                extra={
                    "invoice_id": str(invoice_id),
                    "resolved_po_ids": [
                        str(po_id)
                        for po_id in direct_solution
                    ],
                },
            )
            return await self._finalize_po_resolution(
                invoice_id=invoice_id,
                state=state,
                resolved_set=direct_solution,
                matched_pos=extracted_result.matched_pos,
                candidate_pool=extracted_result.matched_pos,
                vendor_master_id=vendor_master_id,
                pending_issues=pending_issues,
                issue_codes=issue_codes,
                po_reference_missing=po_reference_missing,
            )

        logger.info(
            "Entering PO recovery mode",
            extra={
                "invoice_id": str(invoice_id),
                "extracted_po_count": len(
                    extracted_result.matched_pos,
                ),
            },
        )

        recovery_pos = (
            await self._purchase_order_repo.find_by_vendor_and_statuses(
                vendor_id=vendor_master_id,
                statuses=list(
                    _ACTIVE_PO_STATUSES,
                ),
            )
        )

        candidate_pool = self._build_candidate_pool(
            matched_pos=extracted_result.matched_pos,
            recovery_pos=recovery_pos,
        )
        pre_filter_candidate_pool = list(
            candidate_pool,
        )

        candidate_pool = self._apply_date_filter(
            candidate_pool=candidate_pool,
            invoice_date=invoice.invoice_date,
        )
        candidate_pool = (
            await self._filter_candidates_by_line_overlap(
                candidate_pool=candidate_pool,
                invoice_lines=invoice_lines,
            )
        )

        if not candidate_pool:
            pending_issues.append(
                PendingIssue(
                    issue_code=PO_UNRESOLVED,
                    check_name="candidate_pool",
                    field_name="po_id",
                    issue_type=IssueType.MISSING,
                    expected_value=None,
                    actual_value=None,
                    description=(
                        "No eligible purchase orders found for "
                        "PO resolution."
                    ),
                ),
            )
            pending_issues = (
                await self._attach_candidate_po_context(
                    pending_issues=pending_issues,
                    candidate_pool=(
                        pre_filter_candidate_pool
                        or recovery_pos
                    ),
                    invoice_id=invoice_id,
                )
            )
            issue_codes = await self._persist_issues(
                invoice_id=invoice_id,
                pending_issues=pending_issues,
                issue_codes=issue_codes,
            )
            return await self._return_po_resolution_failure(
                invoice_id=invoice_id,
                issue_codes=issue_codes,
            )

        search_result = await self._search_po_allocations(
            invoice_id=invoice_id,
            invoice_lines=invoice_lines,
            candidate_pool=candidate_pool,
        )
        solutions = search_result.po_sets

        if not solutions:
            pending_issues.append(
                PendingIssue(
                    issue_code=PO_UNRESOLVED,
                    check_name="po_set_search",
                    field_name="po_id",
                    issue_type=IssueType.MISSING,
                    expected_value=None,
                    actual_value=None,
                    description=(
                        "No valid PO set could fully explain "
                        "invoice demand."
                    ),
                ),
            )
            pending_issues = (
                await self._attach_candidate_po_context(
                    pending_issues=pending_issues,
                    candidate_pool=candidate_pool,
                    invoice_id=invoice_id,
                )
            )
            issue_codes = await self._persist_issues(
                invoice_id=invoice_id,
                pending_issues=pending_issues,
                issue_codes=issue_codes,
            )
            return await self._return_po_resolution_failure(
                invoice_id=invoice_id,
                issue_codes=issue_codes,
            )

        if (
            len(solutions) > 1
            or self._is_recovery_ambiguous(
                po_reference_missing=po_reference_missing,
                search_result=search_result,
            )
        ):
            pending_issues.append(
                PendingIssue(
                    issue_code=PO_AMBIGUOUS,
                    check_name="po_set_search",
                    field_name="po_id",
                    issue_type=IssueType.AMBIGUOUS,
                    expected_value=None,
                    actual_value=None,
                    description=(
                        "Multiple valid PO sets were found for "
                        "this invoice."
                    ),
                ),
            )
            pending_issues = (
                await self._attach_candidate_po_context(
                    pending_issues=pending_issues,
                    candidate_pool=candidate_pool,
                    invoice_id=invoice_id,
                    po_set_solutions=solutions,
                )
            )
            issue_codes = await self._persist_issues(
                invoice_id=invoice_id,
                pending_issues=pending_issues,
                issue_codes=issue_codes,
            )
            return await self._return_po_resolution_failure(
                invoice_id=invoice_id,
                issue_codes=issue_codes,
            )

        resolved_set = next(
            iter(solutions),
        )

        return await self._finalize_po_resolution(
            invoice_id=invoice_id,
            state=state,
            resolved_set=resolved_set,
            matched_pos=extracted_result.matched_pos,
            candidate_pool=candidate_pool,
            vendor_master_id=vendor_master_id,
            pending_issues=pending_issues,
            issue_codes=issue_codes,
            po_reference_missing=po_reference_missing,
        )

    async def _return_po_resolution_failure(
        self,
        *,
        invoice_id: UUID,
        issue_codes: list[str],
    ) -> dict[str, Any]:
        await self._clear_po_resolution_artifacts(
            invoice_id,
        )

        return build_validation_state(
            invoice_id=invoice_id,
            po_id=None,
            issue_codes=issue_codes,
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
            "Cleared unresolved PO mappings and pending allocations",
            extra={
                "invoice_id": str(invoice_id),
            },
        )

    @staticmethod
    def _is_recovery_ambiguous(
        *,
        po_reference_missing: bool,
        search_result: _POSearchResult,
    ) -> bool:
        if not po_reference_missing:
            return False

        if search_result.allocation_plan_count > 1:
            return True

        if len(search_result.po_sets) > 1:
            return True

        return False

    async def _try_direct_extracted_po_resolution(
        self,
        invoice_id: UUID,
        invoice_lines: list[InvoiceLineItemRecord],
        matched_pos: list[PurchaseOrderRecord],
    ) -> frozenset[UUID] | None:
        active_matched = [
            purchase_order
            for purchase_order in matched_pos
            if purchase_order.status
            in _ACTIVE_PO_STATUSES
        ]

        if not active_matched:
            return None

        solutions = await self._find_po_set_solutions(
            invoice_id=invoice_id,
            invoice_lines=invoice_lines,
            candidate_pool=active_matched,
        )

        if len(solutions) != 1:
            return None

        return next(
            iter(solutions),
        )

    async def _search_po_allocations(
        self,
        invoice_id: UUID,
        invoice_lines: list[InvoiceLineItemRecord],
        candidate_pool: list[PurchaseOrderRecord],
    ) -> _POSearchResult:
        po_sets = await self._find_po_set_solutions(
            invoice_id=invoice_id,
            invoice_lines=invoice_lines,
            candidate_pool=candidate_pool,
        )

        if not invoice_lines:
            matching_po_ids = {
                purchase_order.id
                for purchase_order in candidate_pool
            }
            return _POSearchResult(
                po_sets=po_sets,
                allocation_plan_count=len(
                    po_sets,
                ),
                matching_po_ids=matching_po_ids,
            )

        po_ids = [
            purchase_order.id
            for purchase_order in candidate_pool
        ]
        po_lines = await self._po_line_item_repo.get_by_po_ids(
            po_ids,
        )

        if not po_lines:
            return _POSearchResult(
                po_sets=po_sets,
                allocation_plan_count=0,
                matching_po_ids=set(),
            )

        matcher = POLineMatcher()
        typed_match_edges = await matcher.build_typed_match_edges(
            invoice_lines=invoice_lines,
            po_lines=po_lines,
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
        allocation_plans = find_all_allocation_plans(
            invoice_line_ids=[
                line.id
                for line in invoice_lines
            ],
            quantity_by_line={
                line.id: line.quantity_billed
                for line in invoice_lines
            },
            match_edges=typed_match_edges,
            po_line_capacity=po_line_capacity,
            po_line_to_po=po_line_to_po,
        )
        matching_po_ids = {
            po_line_to_po[
                edge.po_line_id
            ]
            for edges in typed_match_edges.values()
            for edge in edges
        }

        return _POSearchResult(
            po_sets=po_sets,
            allocation_plan_count=len(
                allocation_plans,
            ),
            matching_po_ids=matching_po_ids,
        )

    async def _finalize_po_resolution(
        self,
        *,
        invoice_id: UUID,
        state: dict[str, Any],
        resolved_set: frozenset[UUID],
        matched_pos: list[PurchaseOrderRecord],
        candidate_pool: list[PurchaseOrderRecord],
        vendor_master_id: UUID,
        pending_issues: list[PendingIssue],
        issue_codes: list[str],
        po_reference_missing: bool = False,
    ) -> dict[str, Any]:
        pending_issues.extend(
            self._detect_invalid_po_references(
                matched_pos=matched_pos,
                resolved_set=resolved_set,
            ),
        )

        vendor_conflict = self._validate_vendor_consistency(
            candidate_pool=candidate_pool,
            resolved_set=resolved_set,
            vendor_master_id=vendor_master_id,
        )

        if vendor_conflict is not None:
            pending_issues.append(
                vendor_conflict,
            )
            pending_issues = (
                await self._attach_candidate_po_context(
                    pending_issues=pending_issues,
                    candidate_pool=candidate_pool,
                    invoice_id=invoice_id,
                )
            )
            issue_codes = await self._persist_issues(
                invoice_id=invoice_id,
                pending_issues=pending_issues,
                issue_codes=issue_codes,
            )
            return await self._return_po_resolution_failure(
                invoice_id=invoice_id,
                issue_codes=issue_codes,
            )

        recoverable_pending = [
            pending_issue
            for pending_issue in pending_issues
            if pending_issue.issue_code
            in _RECOVERABLE_PO_ISSUE_CODES
        ]
        remaining_pending = [
            pending_issue
            for pending_issue in pending_issues
            if pending_issue.issue_code
            not in _RECOVERABLE_PO_ISSUE_CODES
        ]

        recovery_metadata = (
            await self._build_recovery_issue_metadata(
                candidate_pool=candidate_pool,
                invoice_id=invoice_id,
                resolved_po_ids=resolved_set,
            )
        )

        if recoverable_pending:
            recoverable_pending = (
                self._attach_recovery_metadata_to_issues(
                    pending_issues=recoverable_pending,
                    recovery_metadata=recovery_metadata,
                )
            )
            await self._persist_issues(
                invoice_id=invoice_id,
                pending_issues=recoverable_pending,
                issue_codes=issue_codes,
            )

            for issue_code in _RECOVERABLE_PO_ISSUE_CODES:
                await self._validation_issue_repo.mark_issue_resolved(
                    invoice_id,
                    issue_code,
                )

        await self._invoice_po_mapping_repo.create_mappings(
            invoice_id=invoice_id,
            po_ids=sorted(
                resolved_set,
                key=str,
            ),
        )

        if remaining_pending:
            remaining_pending = (
                await self._attach_candidate_po_context(
                    pending_issues=remaining_pending,
                    candidate_pool=candidate_pool,
                    invoice_id=invoice_id,
                )
            )
            remaining_pending = (
                self._attach_recovery_metadata_to_issues(
                    pending_issues=remaining_pending,
                    recovery_metadata=recovery_metadata,
                )
            )

        issue_codes = await self._persist_issues(
            invoice_id=invoice_id,
            pending_issues=remaining_pending,
            issue_codes=issue_codes,
        )
        issue_codes = [
            code
            for code in issue_codes
            if code not in _RECOVERABLE_PO_ISSUE_CODES
        ]

        resolved_po_id = (
            next(iter(resolved_set))
            if len(resolved_set) == 1
            else state.get("po_id")
        )

        logger.info(
            "Completed PO resolution",
            extra={
                "invoice_id": str(invoice_id),
                "resolved_po_ids": [
                    str(po_id)
                    for po_id in resolved_set
                ],
                "issue_codes": issue_codes,
            },
        )

        return build_validation_state(
            invoice_id=invoice_id,
            po_id=resolved_po_id,
            issue_codes=issue_codes,
        )

    async def _validate_extracted_po_numbers(
        self,
        invoice: POResolutionInvoiceRecord,
    ) -> _ExtractedPOResult:
        matched_pos: list[PurchaseOrderRecord] = []
        pending_issues: list[PendingIssue] = []

        if not invoice.po_numbers_extracted:
            pending_issues.append(
                PendingIssue(
                    issue_code=PO_NOT_FOUND,
                    check_name="extracted_po_validation",
                    field_name="po_number",
                    issue_type=IssueType.MISSING,
                    expected_value=None,
                    actual_value=None,
                    description=(
                        "Purchase order number is missing on "
                        "the invoice."
                    ),
                ),
            )
            return _ExtractedPOResult(
                matched_pos=matched_pos,
                pending_issues=tuple(
                    pending_issues,
                ),
            )

        for po_number in invoice.po_numbers_extracted:
            purchase_order = (
                await self._purchase_order_repo.find_by_po_number(
                    po_number,
                )
            )

            if purchase_order is None:
                pending_issues.append(
                    PendingIssue(
                        issue_code=PO_NOT_FOUND,
                        check_name="extracted_po_validation",
                        field_name="po_number",
                        issue_type=IssueType.MISSING,
                        expected_value=None,
                        actual_value=po_number,
                        description=(
                            f"Extracted PO number {po_number} "
                            "was not found in purchase orders."
                        ),
                    ),
                )
                continue

            if purchase_order.status == PurchaseOrderStatus.CLOSED:
                closed_po_lines = (
                    await self._po_line_item_repo.get_by_po_ids(
                        [
                            purchase_order.id,
                        ],
                    )
                )
                closed_po_context = build_po_issue_context(
                    purchase_orders=[
                        purchase_order,
                    ],
                    po_lines=closed_po_lines,
                )
                pending_issues.append(
                    PendingIssue(
                        issue_code=PO_CLOSED,
                        check_name="po_status_validation",
                        field_name="status",
                        issue_type=IssueType.INVALID,
                        expected_value=PurchaseOrderStatus.OPEN.value,
                        actual_value=PurchaseOrderStatus.CLOSED.value,
                        description=append_po_context(
                            (
                                f"Purchase order {po_number} is closed "
                                "and was removed from candidates."
                            ),
                            closed_po_context,
                        ),
                    ),
                )
                continue

            matched_pos.append(
                purchase_order,
            )

        return _ExtractedPOResult(
            matched_pos=matched_pos,
            pending_issues=tuple(
                pending_issues,
            ),
        )

    @staticmethod
    def _build_candidate_pool(
        matched_pos: list[PurchaseOrderRecord],
        recovery_pos: list[PurchaseOrderRecord],
    ) -> list[PurchaseOrderRecord]:
        by_id: dict[UUID, PurchaseOrderRecord] = {}

        for purchase_order in (
            *matched_pos,
            *recovery_pos,
        ):
            if (
                purchase_order.status
                not in _ACTIVE_PO_STATUSES
            ):
                continue

            by_id[
                purchase_order.id
            ] = purchase_order

        return list(
            by_id.values(),
        )

    @staticmethod
    def _apply_date_filter(
        candidate_pool: list[PurchaseOrderRecord],
        invoice_date: date | None,
    ) -> list[PurchaseOrderRecord]:
        if invoice_date is None or not candidate_pool:
            return candidate_pool

        po_dates = {
            purchase_order.id: purchase_order.po_date
            for purchase_order in candidate_pool
        }
        eligible_ids = filter_pos_by_invoice_date(
            po_dates=po_dates,
            invoice_date=invoice_date,
            window_days=settings.PO_DATE_WINDOW_DAYS,
        )

        if not eligible_ids:
            return candidate_pool

        filtered = [
            purchase_order
            for purchase_order in candidate_pool
            if purchase_order.id in eligible_ids
        ]

        return filtered or candidate_pool

    async def _find_po_set_solutions(
        self,
        invoice_id: UUID,
        invoice_lines: list[InvoiceLineItemRecord],
        candidate_pool: list[PurchaseOrderRecord],
    ) -> set[frozenset[UUID]]:
        if not invoice_lines:
            return self._resolve_without_line_items(
                candidate_pool=candidate_pool,
            )

        po_ids = [
            purchase_order.id
            for purchase_order in candidate_pool
        ]
        po_lines = await self._po_line_item_repo.get_by_po_ids(
            po_ids,
        )

        if not po_lines:
            return set()

        matcher = POLineMatcher()
        typed_match_edges = await matcher.build_typed_match_edges(
            invoice_lines=invoice_lines,
            po_lines=po_lines,
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

        allocation_plans = find_all_allocation_plans(
            invoice_line_ids=[
                line.id
                for line in invoice_lines
            ],
            quantity_by_line={
                line.id: line.quantity_billed
                for line in invoice_lines
            },
            match_edges=typed_match_edges,
            po_line_capacity=po_line_capacity,
            po_line_to_po=po_line_to_po,
        )

        return {
            frozenset(
                record.po_id
                for record in plan
            )
            for plan in allocation_plans
        }

    @staticmethod
    def _resolve_without_line_items(
        candidate_pool: list[PurchaseOrderRecord],
    ) -> set[frozenset[UUID]]:
        if len(candidate_pool) == 1:
            return {
                frozenset(
                    {
                        candidate_pool[0].id,
                    },
                ),
            }

        return {
            frozenset(
                {
                    purchase_order.id,
                },
            )
            for purchase_order in candidate_pool
        }

    @staticmethod
    def _detect_invalid_po_references(
        matched_pos: list[PurchaseOrderRecord],
        resolved_set: frozenset[UUID],
    ) -> list[PendingIssue]:
        if not matched_pos:
            return []

        referenced_ids = {
            purchase_order.id
            for purchase_order in matched_pos
        }

        if referenced_ids.intersection(
            resolved_set,
        ):
            return []

        referenced_numbers = ", ".join(
            purchase_order.po_number
            for purchase_order in matched_pos
        )

        return [
            PendingIssue(
                issue_code=INVALID_PO_REFERENCE,
                check_name="invalid_po_reference",
                field_name="po_number",
                issue_type=IssueType.MISMATCH,
                expected_value=None,
                actual_value=referenced_numbers,
                description=(
                    "Invoice referenced purchase order(s) that "
                    "do not match the resolved PO set based on "
                    "line-item coverage."
                ),
            ),
        ]

    @staticmethod
    def _validate_vendor_consistency(
        candidate_pool: list[PurchaseOrderRecord],
        resolved_set: frozenset[UUID],
        vendor_master_id: UUID,
    ) -> PendingIssue | None:
        po_by_id = {
            purchase_order.id: purchase_order
            for purchase_order in candidate_pool
        }

        for po_id in resolved_set:
            purchase_order = po_by_id.get(
                po_id,
            )

            if purchase_order is None:
                continue

            if purchase_order.vendor_id != vendor_master_id:
                return PendingIssue(
                    issue_code=PO_VENDOR_CONFLICT,
                    check_name="vendor_consistency",
                    field_name="vendor_id",
                    issue_type=IssueType.MISMATCH,
                    expected_value=str(
                        vendor_master_id,
                    ),
                    actual_value=(
                        str(purchase_order.vendor_id)
                        if purchase_order.vendor_id is not None
                        else None
                    ),
                    description=(
                        f"Resolved PO {purchase_order.po_number} "
                        "belongs to a different vendor."
                    ),
                )

        return None

    async def _attach_candidate_po_context(
        self,
        pending_issues: list[PendingIssue],
        candidate_pool: list[PurchaseOrderRecord],
        *,
        invoice_id: UUID,
        po_set_solutions: set[frozenset[UUID]] | None = None,
    ) -> list[PendingIssue]:
        if not candidate_pool:
            return pending_issues

        po_lines = await self._po_line_item_repo.get_by_po_ids(
            [
                purchase_order.id
                for purchase_order in candidate_pool
            ],
        )
        quantity_ordered_by_id = {
            po_line.id: po_line.quantity_ordered
            for po_line in po_lines
        }
        available_quantity_by_line_id = (
            await self._po_line_quantity_repo.get_available_quantities(
                po_line_ids=list(
                    quantity_ordered_by_id.keys(),
                ),
                quantity_ordered_by_id=quantity_ordered_by_id,
                exclude_invoice_id=invoice_id,
            )
        )
        context = build_po_issue_context(
            purchase_orders=candidate_pool,
            po_lines=po_lines,
            available_quantity_by_line_id=(
                available_quantity_by_line_id
            ),
            po_set_solutions=po_set_solutions,
        )

        context = build_po_issue_context(
            purchase_orders=candidate_pool,
            po_lines=po_lines,
            available_quantity_by_line_id=(
                available_quantity_by_line_id
            ),
            po_set_solutions=po_set_solutions,
        )
        issue_metadata = build_candidate_pos_metadata(
            purchase_orders=candidate_pool,
            po_lines=po_lines,
            available_quantity_by_line_id=(
                available_quantity_by_line_id
            ),
            po_set_solutions=po_set_solutions,
        )

        return enrich_pending_issues_with_po_context(
            pending_issues,
            context,
            issue_metadata=issue_metadata,
        )

    async def _build_recovery_issue_metadata(
        self,
        *,
        candidate_pool: list[PurchaseOrderRecord],
        invoice_id: UUID,
        resolved_po_ids: frozenset[UUID] | None = None,
        po_set_solutions: set[frozenset[UUID]] | None = None,
    ) -> dict[str, Any]:
        if not candidate_pool:
            return {}

        po_lines = await self._po_line_item_repo.get_by_po_ids(
            [
                purchase_order.id
                for purchase_order in candidate_pool
            ],
        )
        quantity_ordered_by_id = {
            po_line.id: po_line.quantity_ordered
            for po_line in po_lines
        }
        available_quantity_by_line_id = (
            await self._po_line_quantity_repo.get_available_quantities(
                po_line_ids=list(
                    quantity_ordered_by_id.keys(),
                ),
                quantity_ordered_by_id=quantity_ordered_by_id,
                exclude_invoice_id=invoice_id,
            )
        )

        return build_candidate_pos_metadata(
            purchase_orders=candidate_pool,
            po_lines=po_lines,
            available_quantity_by_line_id=(
                available_quantity_by_line_id
            ),
            po_set_solutions=po_set_solutions,
            resolved_po_ids=resolved_po_ids,
        )

    @staticmethod
    def _attach_recovery_metadata_to_issues(
        pending_issues: list[PendingIssue],
        recovery_metadata: dict[str, Any],
    ) -> list[PendingIssue]:
        if not recovery_metadata:
            return pending_issues

        return [
            replace(
                pending_issue,
                metadata={
                    **(
                        pending_issue.metadata or {}
                    ),
                    **recovery_metadata,
                },
            )
            for pending_issue in pending_issues
        ]

    async def _filter_candidates_by_line_overlap(
        self,
        *,
        candidate_pool: list[PurchaseOrderRecord],
        invoice_lines: list[InvoiceLineItemRecord],
    ) -> list[PurchaseOrderRecord]:
        if not candidate_pool or not invoice_lines:
            return candidate_pool

        po_ids = [
            purchase_order.id
            for purchase_order in candidate_pool
        ]
        po_lines = await self._po_line_item_repo.get_by_po_ids(
            po_ids,
        )

        if not po_lines:
            return []

        matcher = POLineMatcher()
        match_edges = await matcher.build_typed_match_edges(
            invoice_lines=invoice_lines,
            po_lines=po_lines,
        )
        po_line_to_po = {
            po_line.id: po_line.po_id
            for po_line in po_lines
        }
        overlapping_po_ids = {
            po_line_to_po[
                edge.po_line_id
            ]
            for edges in match_edges.values()
            for edge in edges
            if edge.po_line_id in po_line_to_po
        }

        return [
            purchase_order
            for purchase_order in candidate_pool
            if purchase_order.id in overlapping_po_ids
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
                    metadata=pending_issue.metadata,
                ),
            )

            if pending_issue.issue_code not in updated_codes:
                updated_codes.append(
                    pending_issue.issue_code,
                )

        return updated_codes

