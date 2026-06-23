from __future__ import annotations

from typing import Any
from uuid import UUID

from src.data.models.postgres.enums import ValidationFlowOutcome

MISSING_PO_COVERAGE = "MISSING_PO_COVERAGE"
VENDOR_NOT_FOUND = "VENDOR_NOT_FOUND"
AMBIGUOUS_VENDOR = "AMBIGUOUS_VENDOR"
DUPLICATE_VENDOR_GSTIN = "DUPLICATE_VENDOR_GSTIN"
PO_MISSING = "PO_MISSING"
PO_UNRESOLVED = "PO_UNRESOLVED"
PO_AMBIGUOUS = "PO_AMBIGUOUS"
PO_RESOLUTION_BLOCKED = "PO_RESOLUTION_BLOCKED"
PO_VENDOR_CONFLICT = "PO_VENDOR_CONFLICT"
UNMATCHED_LINE_ITEM = "UNMATCHED_LINE_ITEM"
AMBIGUOUS_LINE_MATCH = "AMBIGUOUS_LINE_MATCH"
LINE_ITEM_VENDOR_CONFLICT = "LINE_ITEM_VENDOR_CONFLICT"

# Backward compatibility for downstream imports.
PO_NOT_FOUND = PO_MISSING

REROUTE_ISSUE_CODES = frozenset(
    {
        MISSING_PO_COVERAGE,
    },
)

HARD_STOP_ISSUE_CODES = frozenset(
    {
        AMBIGUOUS_VENDOR,
        DUPLICATE_VENDOR_GSTIN,
        PO_UNRESOLVED,
        PO_RESOLUTION_BLOCKED,
        UNMATCHED_LINE_ITEM,
        LINE_ITEM_VENDOR_CONFLICT,
    },
)


def determine_flow_outcome(
    issue_codes: list[str],
) -> ValidationFlowOutcome:
    codes = set(
        issue_codes,
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


def build_validation_state(
    *,
    invoice_id: UUID,
    po_id: object,
    issue_codes: list[str],
) -> dict[str, Any]:
    flow_outcome = determine_flow_outcome(
        issue_codes,
    )

    return {
        "invoice_id": invoice_id,
        "po_id": po_id,
        "issue_codes": issue_codes,
        "flow_outcome": flow_outcome.value,
    }


def preserve_flow_outcome_state(
    *,
    invoice_id: UUID,
    po_id: object,
    issue_codes: list[str],
    flow_outcome: str,
) -> dict[str, Any]:
    return {
        "invoice_id": invoice_id,
        "po_id": po_id,
        "issue_codes": issue_codes,
        "flow_outcome": flow_outcome,
    }


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
