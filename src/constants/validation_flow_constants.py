"""Validation graph flow constants for amount validation and step tracking."""

AMOUNT_VALIDATION_FULL = "full"
AMOUNT_VALIDATION_PARTIAL = "partial"
AMOUNT_VALIDATION_SKIP = "skip"

LINE_ITEM_PARTIAL_AMOUNT_CODES = frozenset(
    {
        "AMBIGUOUS_LINE_MATCH",
        "UNMATCHED_LINE_ITEM",
        "QUANTITY_EXCEEDS_ORDERED",
        "QUANTITY_EXCEEDS_REMAINING",
        "INVALID_ALLOCATION",
    },
)

PO_SKIP_LINE_ITEM_CODES = frozenset(
    {
        "PO_AMBIGUOUS",
        "PO_UNRESOLVED",
    },
)

VALIDATION_STEP_PASSED = "passed"
VALIDATION_STEP_FAILED = "failed"
VALIDATION_STEP_WARNING = "warning"
VALIDATION_STEP_SKIPPED = "skipped"
VALIDATION_STEP_PARTIAL = "partial"
