from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from src.config.settings import settings
from src.control.validation_flow import (
    AMOUNT_VALIDATION_FULL,
    AMOUNT_VALIDATION_PARTIAL,
    preserve_flow_outcome_state,
    merge_validation_steps,
    should_continue_validation,
    should_skip_amount_validation,
    VALIDATION_STEP_FAILED,
    VALIDATION_STEP_PARTIAL,
    VALIDATION_STEP_PASSED,
    VALIDATION_STEP_SKIPPED,
    VALIDATION_STEP_WARNING,
)
from src.data.models.postgres.enums import (
    IssueType,
    ValidationFlowOutcome,
    ValidationIssueStatus,
)
from src.data.repositories.amount_validation.invoice_amount_repository import (
    InvoiceAmountRecord,
    InvoiceAmountRepository,
)
from src.data.repositories.amount_validation.invoice_line_amount_repository import (
    InvoiceLineAmountRecord,
    InvoiceLineAmountRepository,
)
from src.data.repositories.po_resolution.invoice_line_allocation_candidate_repository import (
    InvoiceLineAllocationCandidateRepository,
)
from src.data.repositories.po_resolution.invoice_line_po_allocation_repository import (
    AllocationRecord,
)
from src.data.repositories.po_resolution.invoice_po_resolution_group_repository import (
    InvoicePOResolutionGroupRepository,
)
from src.data.repositories.po_resolution.po_line_item_repository import (
    POLineItemRecord,
    POLineItemRepository,
)
from src.data.repositories.po_resolution.purchase_order_repository import (
    PurchaseOrderRecord,
    PurchaseOrderRepository,
)
from src.data.repositories.shared.validation_issue_repository import (
    ValidationIssueCreate,
    ValidationIssueRepository,
)
from src.utils.amount_validation_utils import (
    amounts_equal,
    decimal_to_str,
    has_positive_amount,
    is_within_variance,
    parse_charges_from_notes,
    sum_decimal_values,
)
from src.utils.tax_details_utils import (
    compute_invoice_line_tax_total,
    normalize_tax_details,
    sum_tax_amounts,
)

logger = logging.getLogger(__name__)

CHECK_STAGE = "amount_validation"

UNIT_PRICE_VARIANCE = "UNIT_PRICE_VARIANCE"
UNIT_PRICE_MISMATCH = "UNIT_PRICE_MISMATCH"
LINE_TOTAL_MISMATCH = "LINE_TOTAL_MISMATCH"
ALLOCATION_AMOUNT_MISMATCH = "ALLOCATION_AMOUNT_MISMATCH"
LINE_TAX_MISMATCH = "LINE_TAX_MISMATCH"
INVOICE_TAX_MISMATCH = "INVOICE_TAX_MISMATCH"
SUBTOTAL_MISMATCH = "SUBTOTAL_MISMATCH"
TOTAL_AMOUNT_MISMATCH = "TOTAL_AMOUNT_MISMATCH"
ADDITIONAL_DISCOUNT_APPLIED = "ADDITIONAL_DISCOUNT_APPLIED"
DISCOUNT_AMOUNT_MISMATCH = "DISCOUNT_AMOUNT_MISMATCH"
ADDITIONAL_HANDLING_FEE = "ADDITIONAL_HANDLING_FEE"
HANDLING_FEE_MISMATCH = "HANDLING_FEE_MISMATCH"
ADDITIONAL_FREIGHT_CHARGE = "ADDITIONAL_FREIGHT_CHARGE"
FREIGHT_CHARGE_MISMATCH = "FREIGHT_CHARGE_MISMATCH"
ADDITIONAL_SHIPPING_CHARGE = "ADDITIONAL_SHIPPING_CHARGE"
SHIPPING_CHARGE_MISMATCH = "SHIPPING_CHARGE_MISMATCH"
ADDITIONAL_PROCESSING_FEE = "ADDITIONAL_PROCESSING_FEE"
PROCESSING_FEE_MISMATCH = "PROCESSING_FEE_MISMATCH"
ADDITIONAL_MISC_CHARGE = "ADDITIONAL_MISC_CHARGE"
MISC_CHARGE_MISMATCH = "MISC_CHARGE_MISMATCH"
ROUNDING_MISMATCH = "ROUNDING_MISMATCH"

_CHARGE_ADDITIONAL_CODES = {
    "handling": ADDITIONAL_HANDLING_FEE,
    "freight": ADDITIONAL_FREIGHT_CHARGE,
    "shipping": ADDITIONAL_SHIPPING_CHARGE,
    "processing": ADDITIONAL_PROCESSING_FEE,
    "misc": ADDITIONAL_MISC_CHARGE,
}

_CHARGE_MISMATCH_CODES = {
    "handling": HANDLING_FEE_MISMATCH,
    "freight": FREIGHT_CHARGE_MISMATCH,
    "shipping": SHIPPING_CHARGE_MISMATCH,
    "processing": PROCESSING_FEE_MISMATCH,
    "misc": MISC_CHARGE_MISMATCH,
}

_AMOUNT_ISSUE_CODES = frozenset(
    {
        UNIT_PRICE_VARIANCE,
        UNIT_PRICE_MISMATCH,
        LINE_TOTAL_MISMATCH,
        ALLOCATION_AMOUNT_MISMATCH,
        LINE_TAX_MISMATCH,
        INVOICE_TAX_MISMATCH,
        SUBTOTAL_MISMATCH,
        TOTAL_AMOUNT_MISMATCH,
        ADDITIONAL_DISCOUNT_APPLIED,
        DISCOUNT_AMOUNT_MISMATCH,
        ADDITIONAL_HANDLING_FEE,
        HANDLING_FEE_MISMATCH,
        ADDITIONAL_FREIGHT_CHARGE,
        FREIGHT_CHARGE_MISMATCH,
        ADDITIONAL_SHIPPING_CHARGE,
        SHIPPING_CHARGE_MISMATCH,
        ADDITIONAL_PROCESSING_FEE,
        PROCESSING_FEE_MISMATCH,
        ADDITIONAL_MISC_CHARGE,
        MISC_CHARGE_MISMATCH,
        ROUNDING_MISMATCH,
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


class AmountValidationAgent:
    def __init__(
        self,
        invoice_amount_repo: InvoiceAmountRepository,
        invoice_line_amount_repo: InvoiceLineAmountRepository,
        allocation_candidate_repo: InvoiceLineAllocationCandidateRepository,
        resolution_group_repo: InvoicePOResolutionGroupRepository,
        po_line_item_repo: POLineItemRepository,
        purchase_order_repo: PurchaseOrderRepository,
        validation_issue_repo: ValidationIssueRepository,
    ) -> None:
        self._invoice_amount_repo = invoice_amount_repo
        self._invoice_line_amount_repo = invoice_line_amount_repo
        self._allocation_candidate_repo = allocation_candidate_repo
        self._resolution_group_repo = resolution_group_repo
        self._po_line_item_repo = po_line_item_repo
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
        flow_outcome = str(
            state.get(
                "flow_outcome",
                ValidationFlowOutcome.CONTINUE.value,
            ),
        )

        logger.info(
            "Starting amount validation",
            extra={
                "invoice_id": str(invoice_id),
                "flow_outcome": flow_outcome,
            },
        )

        if should_skip_amount_validation(
            state,
        ):
            logger.info(
                "Skipping amount validation after unresolved PO",
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
                state=state,
                validation_steps=merge_validation_steps(
                    state,
                    amount_validation=VALIDATION_STEP_SKIPPED,
                ),
            )

        if not should_continue_validation(
            state,
        ):
            logger.info(
                "Skipping amount validation due to flow stop",
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
                state=state,
                validation_steps=merge_validation_steps(
                    state,
                    amount_validation=VALIDATION_STEP_SKIPPED,
                ),
            )

        amount_mode = str(
            state.get(
                "amount_validation_mode",
                AMOUNT_VALIDATION_FULL,
            ),
        )
        partial_validation = amount_mode == AMOUNT_VALIDATION_PARTIAL

        allocations = (
            await self._allocation_candidate_repo.get_validation_allocations_for_invoice(
                invoice_id,
            )
        )

        if not allocations and not partial_validation:
            logger.info(
                "Skipping amount validation; no allocation candidates found",
                extra={
                    "invoice_id": str(invoice_id),
                },
            )
            return preserve_flow_outcome_state(
                invoice_id=invoice_id,
                po_id=state.get("po_id"),
                issue_codes=issue_codes,
                flow_outcome=flow_outcome,
                state=state,
                validation_steps=merge_validation_steps(
                    state,
                    amount_validation=VALIDATION_STEP_SKIPPED,
                ),
            )

        invoice = await self._invoice_amount_repo.get_by_invoice_id(
            invoice_id,
        )

        if invoice is None:
            return preserve_flow_outcome_state(
                invoice_id=invoice_id,
                po_id=state.get("po_id"),
                issue_codes=issue_codes,
                flow_outcome=flow_outcome,
            )

        invoice_lines = (
            await self._invoice_line_amount_repo.get_by_invoice_id(
                invoice_id,
            )
        )
        po_ids = (
            await self._resolution_group_repo.get_candidate_po_ids_for_validation(
                invoice_id,
            )
        )
        po_lines = await self._po_line_item_repo.get_by_po_ids(
            po_ids,
        )
        purchase_orders = await self._purchase_order_repo.get_by_ids(
            po_ids,
        )

        line_by_id = {
            line.id: line
            for line in invoice_lines
        }
        po_line_by_id = {
            po_line.id: po_line
            for po_line in po_lines
        }

        pending_issues: list[PendingIssue] = []

        if partial_validation:
            pending_issues.extend(
                self._validate_line_totals(
                    invoice_lines=invoice_lines,
                ),
            )
            pending_issues.extend(
                self._validate_invoice_tax(
                    invoice=invoice,
                    invoice_lines=invoice_lines,
                ),
            )
            pending_issues.extend(
                self._validate_subtotal(
                    invoice=invoice,
                    invoice_lines=invoice_lines,
                ),
            )
            invoice_charges = parse_charges_from_notes(
                invoice.notes,
            )
            pending_issues.extend(
                self._validate_grand_total(
                    invoice=invoice,
                    invoice_charges=invoice_charges,
                ),
            )
            pending_issues.extend(
                self._validate_rounding(
                    invoice=invoice,
                    invoice_lines=invoice_lines,
                    invoice_charges=invoice_charges,
                ),
            )
        else:
            pending_issues.extend(
                self._validate_unit_prices(
                    allocations=allocations,
                    line_by_id=line_by_id,
                    po_line_by_id=po_line_by_id,
                ),
            )
            pending_issues.extend(
                self._validate_line_totals(
                    invoice_lines=invoice_lines,
                ),
            )
            pending_issues.extend(
                self._validate_allocation_amounts(
                    allocations=allocations,
                    line_by_id=line_by_id,
                ),
            )
            pending_issues.extend(
                self._validate_line_taxes(
                    allocations=allocations,
                    line_by_id=line_by_id,
                    po_line_by_id=po_line_by_id,
                ),
            )
            pending_issues.extend(
                self._validate_invoice_tax(
                    invoice=invoice,
                    invoice_lines=invoice_lines,
                ),
            )
            pending_issues.extend(
                self._validate_subtotal(
                    invoice=invoice,
                    invoice_lines=invoice_lines,
                ),
            )

            invoice_charges = parse_charges_from_notes(
                invoice.notes,
            )
            po_charges = self._aggregate_po_charges(
                purchase_orders=purchase_orders,
            )

            pending_issues.extend(
                self._validate_discounts(
                    invoice=invoice,
                    purchase_orders=purchase_orders,
                ),
            )
            pending_issues.extend(
                self._validate_additional_charges(
                    invoice_charges=invoice_charges,
                    po_charges=po_charges,
                ),
            )
            pending_issues.extend(
                self._validate_charge_mismatches(
                    invoice_charges=invoice_charges,
                    po_charges=po_charges,
                ),
            )
            pending_issues.extend(
                self._validate_grand_total(
                    invoice=invoice,
                    invoice_charges=invoice_charges,
                ),
            )
            pending_issues.extend(
                self._validate_rounding(
                    invoice=invoice,
                    invoice_lines=invoice_lines,
                    invoice_charges=invoice_charges,
                ),
            )

        issue_codes = await self._persist_issues(
            invoice_id=invoice_id,
            pending_issues=pending_issues,
            issue_codes=issue_codes,
        )

        detected_codes = {
            pending_issue.issue_code
            for pending_issue in pending_issues
        }

        for issue_code in _AMOUNT_ISSUE_CODES:
            if issue_code in detected_codes:
                continue

            await self._validation_issue_repo.mark_issue_resolved(
                invoice_id,
                issue_code,
            )
            issue_codes = [
                code
                for code in issue_codes
                if code != issue_code
            ]

        logger.info(
            "Completed amount validation",
            extra={
                "invoice_id": str(invoice_id),
                "issue_count": len(pending_issues),
                "issue_codes": issue_codes,
            },
        )

        amount_step_status = (
            VALIDATION_STEP_PARTIAL
            if partial_validation
            else (
                VALIDATION_STEP_WARNING
                if pending_issues
                else VALIDATION_STEP_PASSED
            )
        )

        return preserve_flow_outcome_state(
            invoice_id=invoice_id,
            po_id=state.get("po_id"),
            issue_codes=issue_codes,
            flow_outcome=flow_outcome,
            state=state,
            amount_validation_mode=amount_mode,
            validation_steps=merge_validation_steps(
                state,
                amount_validation=amount_step_status,
            ),
        )

    def _validate_unit_prices(
        self,
        allocations: list[AllocationRecord],
        line_by_id: dict[UUID, InvoiceLineAmountRecord],
        po_line_by_id: dict[UUID, POLineItemRecord],
    ) -> list[PendingIssue]:
        issues: list[PendingIssue] = []
        tolerance = settings.UNIT_PRICE_VARIANCE_TOLERANCE
        checked: set[tuple[UUID, UUID]] = set()

        for allocation in allocations:
            key = (
                allocation.invoice_line_item_id,
                allocation.po_line_item_id,
            )

            if key in checked:
                continue

            checked.add(
                key,
            )

            invoice_line = line_by_id.get(
                allocation.invoice_line_item_id,
            )
            po_line = po_line_by_id.get(
                allocation.po_line_item_id,
            )

            if invoice_line is None or po_line is None:
                continue

            invoice_price = invoice_line.unit_price
            po_price = po_line.unit_price

            if amounts_equal(
                po_price,
                invoice_price,
                tolerance=Decimal(0),
            ):
                continue

            if is_within_variance(
                po_price,
                invoice_price,
                tolerance=tolerance,
            ):
                issues.append(
                    PendingIssue(
                        issue_code=UNIT_PRICE_VARIANCE,
                        check_name="unit_price_validation",
                        field_name="unit_price",
                        issue_type=IssueType.WARNING,
                        expected_value=decimal_to_str(
                            po_price,
                        ),
                        actual_value=decimal_to_str(
                            invoice_price,
                        ),
                        description=(
                            "Invoice unit price is within configured "
                            "variance tolerance of PO unit price."
                        ),
                    ),
                )
                continue

            issues.append(
                PendingIssue(
                    issue_code=UNIT_PRICE_MISMATCH,
                    check_name="unit_price_validation",
                    field_name="unit_price",
                    issue_type=IssueType.MISMATCH,
                    expected_value=decimal_to_str(
                        po_price,
                    ),
                    actual_value=decimal_to_str(
                        invoice_price,
                    ),
                    description=(
                        "Invoice unit price does not match PO unit "
                        "price beyond tolerance."
                    ),
                ),
            )

        return issues

    def _validate_line_totals(
        self,
        invoice_lines: list[InvoiceLineAmountRecord],
    ) -> list[PendingIssue]:
        issues: list[PendingIssue] = []
        tolerance = settings.AMOUNT_ROUNDING_TOLERANCE

        for line in invoice_lines:
            discount = line.discount_amount or Decimal(0)
            expected = (
                line.quantity_billed * line.unit_price
                - discount
            ).quantize(
                Decimal("0.01"),
            )

            if amounts_equal(
                expected,
                line.line_total,
                tolerance=tolerance,
            ):
                continue

            issues.append(
                PendingIssue(
                    issue_code=LINE_TOTAL_MISMATCH,
                    check_name="line_total_validation",
                    field_name="line_total",
                    issue_type=IssueType.MISMATCH,
                    expected_value=decimal_to_str(
                        expected,
                    ),
                    actual_value=decimal_to_str(
                        line.line_total,
                    ),
                    description=(
                        "Computed line total does not match invoice "
                        "line total."
                    ),
                ),
            )

        return issues

    def _validate_allocation_amounts(
        self,
        allocations: list[AllocationRecord],
        line_by_id: dict[UUID, InvoiceLineAmountRecord],
    ) -> list[PendingIssue]:
        issues: list[PendingIssue] = []
        tolerance = settings.AMOUNT_ROUNDING_TOLERANCE
        allocated_by_line: dict[UUID, Decimal] = defaultdict(
            Decimal,
        )

        for allocation in allocations:
            allocated_by_line[
                allocation.invoice_line_item_id
            ] += allocation.allocated_amount

        for line_id, allocated_amount in (
            allocated_by_line.items()
        ):
            invoice_line = line_by_id.get(
                line_id,
            )

            if invoice_line is None:
                continue

            discount = invoice_line.discount_amount or Decimal(0)
            expected = (
                invoice_line.quantity_billed
                * invoice_line.unit_price
                - discount
            ).quantize(
                Decimal("0.01"),
            )
            actual = allocated_amount.quantize(
                Decimal("0.01"),
            )

            if amounts_equal(
                expected,
                actual,
                tolerance=tolerance,
            ):
                continue

            issues.append(
                PendingIssue(
                    issue_code=ALLOCATION_AMOUNT_MISMATCH,
                    check_name="allocation_amount_validation",
                    field_name="allocated_amount",
                    issue_type=IssueType.MISMATCH,
                    expected_value=decimal_to_str(
                        expected,
                    ),
                    actual_value=decimal_to_str(
                        actual,
                    ),
                    description=(
                        "Allocated line amounts do not reconcile "
                        "with invoice line amount."
                    ),
                ),
            )

        return issues

    def _validate_line_taxes(
        self,
        allocations: list[AllocationRecord],
        line_by_id: dict[UUID, InvoiceLineAmountRecord],
        po_line_by_id: dict[UUID, POLineItemRecord],
    ) -> list[PendingIssue]:
        issues: list[PendingIssue] = []
        tolerance = settings.AMOUNT_ROUNDING_TOLERANCE
        checked_lines: set[UUID] = set()

        for allocation in allocations:
            line_id = allocation.invoice_line_item_id

            if line_id in checked_lines:
                continue

            checked_lines.add(
                line_id,
            )

            invoice_line = line_by_id.get(
                line_id,
            )
            po_line = po_line_by_id.get(
                allocation.po_line_item_id,
            )

            if invoice_line is None or po_line is None:
                continue

            invoice_tax_details = normalize_tax_details(
                invoice_line.tax_details,
            )
            po_tax_details = normalize_tax_details(
                po_line.tax_details,
            )

            if not invoice_tax_details:
                continue

            invoice_base = (
                invoice_line.quantity_billed
                * invoice_line.unit_price
                - (invoice_line.discount_amount or Decimal(0))
            ).quantize(
                Decimal("0.01"),
            )
            po_base = (
                allocation.allocated_quantity
                * po_line.unit_price
                - (po_line.discount_amount or Decimal(0))
            ).quantize(
                Decimal("0.01"),
            )

            invoice_tax = sum_tax_amounts(
                invoice_tax_details,
                invoice_base,
            )
            expected_tax = sum_tax_amounts(
                po_tax_details,
                po_base,
            )

            if amounts_equal(
                expected_tax,
                invoice_tax,
                tolerance=tolerance,
            ):
                continue

            issues.append(
                PendingIssue(
                    issue_code=LINE_TAX_MISMATCH,
                    check_name="line_tax_validation",
                    field_name="tax_details",
                    issue_type=IssueType.MISMATCH,
                    expected_value=decimal_to_str(
                        expected_tax,
                    ),
                    actual_value=decimal_to_str(
                        invoice_tax,
                    ),
                    description=(
                        "Invoice line tax does not match expected "
                        "tax from PO line."
                    ),
                ),
            )

        return issues

    def _validate_invoice_tax(
        self,
        invoice: InvoiceAmountRecord,
        invoice_lines: list[InvoiceLineAmountRecord],
    ) -> list[PendingIssue]:
        if invoice.tax_amount is None:
            return []

        tolerance = settings.AMOUNT_ROUNDING_TOLERANCE
        computed_tax = compute_invoice_line_tax_total(
            invoice_lines,
            header_tax_amount=invoice.tax_amount,
        )

        if amounts_equal(
            computed_tax,
            invoice.tax_amount,
            tolerance=tolerance,
        ):
            return []

        return [
            PendingIssue(
                issue_code=INVOICE_TAX_MISMATCH,
                check_name="invoice_tax_validation",
                field_name="tax_amount",
                issue_type=IssueType.MISMATCH,
                expected_value=decimal_to_str(
                    computed_tax,
                ),
                actual_value=decimal_to_str(
                    invoice.tax_amount,
                ),
                description=(
                    "Sum of line taxes does not match invoice tax "
                    "amount."
                ),
            ),
        ]

    def _validate_subtotal(
        self,
        invoice: InvoiceAmountRecord,
        invoice_lines: list[InvoiceLineAmountRecord],
    ) -> list[PendingIssue]:
        if invoice.subtotal_amount is None:
            return []

        tolerance = settings.AMOUNT_ROUNDING_TOLERANCE
        computed_subtotal = sum_decimal_values(
            [
                line.line_total
                for line in invoice_lines
            ],
        )

        if amounts_equal(
            computed_subtotal,
            invoice.subtotal_amount,
            tolerance=tolerance,
        ):
            return []

        return [
            PendingIssue(
                issue_code=SUBTOTAL_MISMATCH,
                check_name="subtotal_validation",
                field_name="subtotal_amount",
                issue_type=IssueType.MISMATCH,
                expected_value=decimal_to_str(
                    computed_subtotal,
                ),
                actual_value=decimal_to_str(
                    invoice.subtotal_amount,
                ),
                description=(
                    "Sum of line totals does not match invoice "
                    "subtotal."
                ),
            ),
        ]

    def _validate_grand_total(
        self,
        invoice: InvoiceAmountRecord,
        invoice_charges: dict[str, Decimal],
    ) -> list[PendingIssue]:
        if invoice.total_amount is None:
            return []

        tolerance = settings.AMOUNT_ROUNDING_TOLERANCE
        subtotal = invoice.subtotal_amount or Decimal(0)
        tax = invoice.tax_amount or Decimal(0)
        discount = invoice.discount_amount or Decimal(0)
        additional = sum_decimal_values(
            list(
                invoice_charges.values(),
            ),
        )
        expected_total = (
            subtotal + tax - discount + additional
        ).quantize(
            Decimal("0.01"),
        )

        if amounts_equal(
            expected_total,
            invoice.total_amount,
            tolerance=tolerance,
        ):
            return []

        return [
            PendingIssue(
                issue_code=TOTAL_AMOUNT_MISMATCH,
                check_name="grand_total_validation",
                field_name="total_amount",
                issue_type=IssueType.MISMATCH,
                expected_value=decimal_to_str(
                    expected_total,
                ),
                actual_value=decimal_to_str(
                    invoice.total_amount,
                ),
                description=(
                    "Computed grand total does not match invoice "
                    "total amount."
                ),
            ),
        ]

    def _validate_discounts(
        self,
        invoice: InvoiceAmountRecord,
        purchase_orders: list[PurchaseOrderRecord],
    ) -> list[PendingIssue]:
        invoice_discount = invoice.discount_amount or Decimal(0)

        if not has_positive_amount(
            invoice_discount,
        ):
            return []

        po_discount = sum_decimal_values(
            [
                purchase_order.discount_amount
                for purchase_order in purchase_orders
            ],
        )

        if not has_positive_amount(
            po_discount,
        ):
            return [
                PendingIssue(
                    issue_code=ADDITIONAL_DISCOUNT_APPLIED,
                    check_name="discount_validation",
                    field_name="discount_amount",
                    issue_type=IssueType.WARNING,
                    expected_value=decimal_to_str(
                        po_discount,
                    ),
                    actual_value=decimal_to_str(
                        invoice_discount,
                    ),
                    description=(
                        "Invoice contains a discount that is not "
                        "present on resolved purchase orders."
                    ),
                ),
            ]

        if amounts_equal(
            po_discount,
            invoice_discount,
            tolerance=settings.AMOUNT_ROUNDING_TOLERANCE,
        ):
            return []

        return [
            PendingIssue(
                issue_code=DISCOUNT_AMOUNT_MISMATCH,
                check_name="discount_validation",
                field_name="discount_amount",
                issue_type=IssueType.MISMATCH,
                expected_value=decimal_to_str(
                    po_discount,
                ),
                actual_value=decimal_to_str(
                    invoice_discount,
                ),
                description=(
                    "Invoice discount amount does not match PO "
                    "discount amount."
                ),
            ),
        ]

    def _validate_additional_charges(
        self,
        invoice_charges: dict[str, Decimal],
        po_charges: dict[str, Decimal],
    ) -> list[PendingIssue]:
        issues: list[PendingIssue] = []

        for charge_type, amount in invoice_charges.items():
            if charge_type in po_charges:
                continue

            issue_code = _CHARGE_ADDITIONAL_CODES.get(
                charge_type,
            )

            if issue_code is None:
                continue

            issues.append(
                PendingIssue(
                    issue_code=issue_code,
                    check_name="additional_charge_detection",
                    field_name=charge_type,
                    issue_type=IssueType.WARNING,
                    expected_value=None,
                    actual_value=decimal_to_str(
                        amount,
                    ),
                    description=(
                        f"Additional {charge_type} charge detected "
                        "on invoice and absent from PO."
                    ),
                ),
            )

        return issues

    def _validate_charge_mismatches(
        self,
        invoice_charges: dict[str, Decimal],
        po_charges: dict[str, Decimal],
    ) -> list[PendingIssue]:
        issues: list[PendingIssue] = []
        tolerance = settings.AMOUNT_ROUNDING_TOLERANCE

        for charge_type, invoice_amount in (
            invoice_charges.items()
        ):
            po_amount = po_charges.get(
                charge_type,
            )

            if po_amount is None:
                continue

            if amounts_equal(
                po_amount,
                invoice_amount,
                tolerance=tolerance,
            ):
                continue

            issue_code = _CHARGE_MISMATCH_CODES.get(
                charge_type,
            )

            if issue_code is None:
                continue

            issues.append(
                PendingIssue(
                    issue_code=issue_code,
                    check_name="charge_mismatch_validation",
                    field_name=charge_type,
                    issue_type=IssueType.MISMATCH,
                    expected_value=decimal_to_str(
                        po_amount,
                    ),
                    actual_value=decimal_to_str(
                        invoice_amount,
                    ),
                    description=(
                        f"{charge_type.title()} charge amount "
                        "differs between invoice and PO."
                    ),
                ),
            )

        return issues

    def _validate_rounding(
        self,
        invoice: InvoiceAmountRecord,
        invoice_lines: list[InvoiceLineAmountRecord],
        invoice_charges: dict[str, Decimal],
    ) -> list[PendingIssue]:
        if invoice.total_amount is None:
            return []

        threshold = settings.AMOUNT_ROUNDING_TOLERANCE
        subtotal = invoice.subtotal_amount or sum_decimal_values(
            [
                line.line_total
                for line in invoice_lines
            ],
        )
        tax = invoice.tax_amount or Decimal(0)
        discount = invoice.discount_amount or Decimal(0)
        additional = sum_decimal_values(
            list(
                invoice_charges.values(),
            ),
        )
        expected_total = (
            subtotal + tax - discount + additional
        ).quantize(
            Decimal("0.01"),
        )
        difference = abs(
            expected_total - invoice.total_amount,
        )

        if difference <= threshold:
            return []

        return [
            PendingIssue(
                issue_code=ROUNDING_MISMATCH,
                check_name="rounding_validation",
                field_name="total_amount",
                issue_type=IssueType.MISMATCH,
                expected_value=decimal_to_str(
                    expected_total,
                ),
                actual_value=decimal_to_str(
                    invoice.total_amount,
                ),
                description=(
                    "Invoice total differs from computed total "
                    "beyond configured rounding threshold."
                ),
            ),
        ]

    @staticmethod
    def _aggregate_po_charges(
        purchase_orders: list[PurchaseOrderRecord],
    ) -> dict[str, Decimal]:
        aggregated: dict[str, Decimal] = {}

        for purchase_order in purchase_orders:
            # PO model has no dedicated charge fields; charges are
            # not currently extracted for purchase orders.
            _ = purchase_order

        return aggregated

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
