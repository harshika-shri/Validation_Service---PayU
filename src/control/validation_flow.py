from __future__ import annotations

from typing import Any
from uuid import UUID

from src.constants import validation_issue_codes as issue_codes
from src.constants.validation_flow_constants import (
    AMOUNT_VALIDATION_FULL,
    AMOUNT_VALIDATION_PARTIAL,
    AMOUNT_VALIDATION_SKIP,
    LINE_ITEM_PARTIAL_AMOUNT_CODES,
    VALIDATION_STEP_FAILED,
    VALIDATION_STEP_PARTIAL,
    VALIDATION_STEP_PASSED,
    VALIDATION_STEP_SKIPPED,
    VALIDATION_STEP_WARNING,
)
from src.data.models.postgres.enums import ValidationFlowOutcome

# Backward compatibility for downstream imports.
MISSING_PO_COVERAGE = issue_codes.MISSING_PO_COVERAGE
VENDOR_NOT_FOUND = issue_codes.VENDOR_NOT_FOUND
AMBIGUOUS_VENDOR = issue_codes.AMBIGUOUS_VENDOR
DUPLICATE_VENDOR_GSTIN = issue_codes.DUPLICATE_VENDOR_GSTIN
PO_MISSING = issue_codes.PO_MISSING
PO_NOT_FOUND = PO_MISSING
PO_UNRESOLVED = issue_codes.PO_UNRESOLVED
PO_AMBIGUOUS = issue_codes.PO_AMBIGUOUS
PO_RESOLUTION_BLOCKED = issue_codes.PO_RESOLUTION_BLOCKED
PO_VENDOR_CONFLICT = issue_codes.PO_VENDOR_CONFLICT
UNMATCHED_LINE_ITEM = issue_codes.UNMATCHED_LINE_ITEM
AMBIGUOUS_LINE_MATCH = issue_codes.AMBIGUOUS_LINE_MATCH
LINE_ITEM_VENDOR_CONFLICT = issue_codes.LINE_ITEM_VENDOR_CONFLICT

REROUTE_ISSUE_CODES = issue_codes.REROUTE_ISSUE_CODES
HARD_STOP_ISSUE_CODES = issue_codes.HARD_STOP_ISSUE_CODES


def determine_flow_outcome(
    issue_codes_list: list[str],
) -> ValidationFlowOutcome:
    codes = set(
        issue_codes_list,
    )

    if codes.intersection(
        REROUTE_ISSUE_CODES,
    ):
        return ValidationFlowOutcome.REROUTE

    if codes.intersection(
        HARD_STOP_ISSUE_CODES,
    ):
        return ValidationFlowOutcome.HARD_STOP

    return ValidationFlowOutcome.CONTINUE


def merge_validation_steps(
    state: dict[str, Any],
    **step_updates: str,
) -> dict[str, str]:
    merged = dict(
        state.get(
            "validation_steps",
            {},
        )
        or {},
    )
    merged.update(
        step_updates,
    )
    return merged


def needs_partial_amount_validation(
    issue_codes: list[str],
) -> bool:
    return bool(
        set(
            issue_codes,
        ).intersection(
            LINE_ITEM_PARTIAL_AMOUNT_CODES,
        )
    )


def build_validation_state(
    *,
    invoice_id: UUID,
    po_id: object,
    issue_codes: list[str],
    state: dict[str, Any] | None = None,
    amount_validation_mode: str | None = None,
    skip_line_item_validation: bool | None = None,
    validation_steps: dict[str, str] | None = None,
) -> dict[str, Any]:
    flow_outcome = determine_flow_outcome(
        issue_codes,
    )
    resolved_amount_mode = amount_validation_mode

    if resolved_amount_mode is None and state is not None:
        resolved_amount_mode = state.get(
            "amount_validation_mode",
            AMOUNT_VALIDATION_FULL,
        )

    if resolved_amount_mode is None:
        resolved_amount_mode = AMOUNT_VALIDATION_FULL

    if needs_partial_amount_validation(
        issue_codes,
    ):
        resolved_amount_mode = AMOUNT_VALIDATION_PARTIAL

    result: dict[str, Any] = {
        "invoice_id": invoice_id,
        "po_id": po_id,
        "issue_codes": issue_codes,
        "flow_outcome": flow_outcome.value,
        "amount_validation_mode": resolved_amount_mode,
    }

    if state is not None:
        result["po_reroute_count"] = state.get(
            "po_reroute_count",
            0,
        )
        result["validation_steps"] = dict(
            state.get(
                "validation_steps",
                {},
            )
            or {},
        )

    if skip_line_item_validation is not None:
        result["skip_line_item_validation"] = skip_line_item_validation
    elif state is not None:
        result["skip_line_item_validation"] = bool(
            state.get(
                "skip_line_item_validation",
                False,
            ),
        )
    else:
        result["skip_line_item_validation"] = False

    if validation_steps is not None:
        result["validation_steps"] = validation_steps

    return result


def preserve_flow_outcome_state(
    *,
    invoice_id: UUID,
    po_id: object,
    issue_codes: list[str],
    flow_outcome: str,
    state: dict[str, Any] | None = None,
    amount_validation_mode: str | None = None,
    skip_line_item_validation: bool | None = None,
    validation_steps: dict[str, str] | None = None,
) -> dict[str, Any]:
    resolved_amount_mode = amount_validation_mode

    if resolved_amount_mode is None and state is not None:
        resolved_amount_mode = state.get(
            "amount_validation_mode",
            AMOUNT_VALIDATION_FULL,
        )

    if resolved_amount_mode is None:
        resolved_amount_mode = AMOUNT_VALIDATION_FULL

    if needs_partial_amount_validation(
        issue_codes,
    ):
        resolved_amount_mode = AMOUNT_VALIDATION_PARTIAL

    result: dict[str, Any] = {
        "invoice_id": invoice_id,
        "po_id": po_id,
        "issue_codes": issue_codes,
        "flow_outcome": flow_outcome,
        "amount_validation_mode": resolved_amount_mode,
    }

    if state is not None:
        result["po_reroute_count"] = state.get(
            "po_reroute_count",
            0,
        )
        result["validation_steps"] = dict(
            state.get(
                "validation_steps",
                {},
            )
            or {},
        )
        result["skip_line_item_validation"] = bool(
            state.get(
                "skip_line_item_validation",
                False,
            ),
        )
    else:
        result["skip_line_item_validation"] = False
        result["validation_steps"] = {}

    if skip_line_item_validation is not None:
        result["skip_line_item_validation"] = skip_line_item_validation

    if validation_steps is not None:
        result["validation_steps"] = validation_steps

    return result


def should_continue_validation(
    state: dict[str, Any],
) -> bool:
    return (
        state.get(
            "flow_outcome",
            ValidationFlowOutcome.CONTINUE.value,
        )
        == ValidationFlowOutcome.CONTINUE.value
    )


def should_skip_amount_validation(
    state: dict[str, Any],
) -> bool:
    return (
        state.get(
            "amount_validation_mode",
            AMOUNT_VALIDATION_FULL,
        )
        == AMOUNT_VALIDATION_SKIP
    )
