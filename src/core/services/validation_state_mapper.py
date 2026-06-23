from __future__ import annotations

from typing import cast
from uuid import UUID

from src.data.models.postgres.enums import (
    InvoiceValidationDecision,
    InvoiceValidationOutcome,
    ValidationFlowOutcome,
)
from src.schemas.validation_state_schema import (
    ReviewSummarySchema,
    ValidationStateSchema,
)


def validation_state_to_schema(
    state: dict[str, object],
) -> ValidationStateSchema:
    flow_outcome_value = str(
        state.get(
            "flow_outcome",
            ValidationFlowOutcome.CONTINUE.value,
        ),
    )

    if flow_outcome_value == "end":
        flow_outcome_value = ValidationFlowOutcome.CONTINUE.value
    decision_value = state.get(
        "decision",
    )
    invoice_status_value = state.get(
        "invoice_status",
    )
    review_summary_value = state.get(
        "review_summary",
    )

    return ValidationStateSchema(
        invoice_id=cast(
            UUID,
            state["invoice_id"],
        ),
        po_id=cast(
            UUID | None,
            state.get("po_id"),
        ),
        issue_codes=cast(
            list[str],
            state.get(
                "issue_codes",
                [],
            ),
        ),
        open_issue_codes=cast(
            list[str],
            state.get(
                "open_issue_codes",
                [],
            ),
        ),
        flow_outcome=ValidationFlowOutcome(
            flow_outcome_value,
        ),
        decision=(
            InvoiceValidationDecision(
                cast(
                    str,
                    decision_value,
                ),
            )
            if decision_value is not None
            else None
        ),
        invoice_status=(
            InvoiceValidationOutcome(
                cast(
                    str,
                    invoice_status_value,
                ),
            )
            if invoice_status_value is not None
            else None
        ),
        review_summary=(
            ReviewSummarySchema(
                id=UUID(
                    cast(
                        str,
                        cast(
                            dict[str, object],
                            review_summary_value,
                        )["id"],
                    ),
                ),
                decision=cast(
                    str,
                    cast(
                        dict[str, object],
                        review_summary_value,
                    )["decision"],
                ),
                executive_summary=cast(
                    str,
                    cast(
                        dict[str, object],
                        review_summary_value,
                    )["executive_summary"],
                ),
                system_recoveries=cast(
                    list[str],
                    cast(
                        dict[str, object],
                        review_summary_value,
                    ).get(
                        "system_recoveries",
                        [],
                    ),
                ),
                open_issues=cast(
                    list[str],
                    cast(
                        dict[str, object],
                        review_summary_value,
                    ).get(
                        "open_issues",
                        [],
                    ),
                ),
                vendor_clarifications=cast(
                    list[str],
                    cast(
                        dict[str, object],
                        review_summary_value,
                    ).get(
                        "vendor_clarifications",
                        [],
                    ),
                ),
                resolved_po_numbers=cast(
                    list[str],
                    cast(
                        dict[str, object],
                        review_summary_value,
                    ).get(
                        "resolved_po_numbers",
                        [],
                    ),
                ),
            )
            if isinstance(
                review_summary_value,
                dict,
            )
            else None
        ),
    )
