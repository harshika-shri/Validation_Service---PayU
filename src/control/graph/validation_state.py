from __future__ import annotations

from typing import Any, TypedDict
from uuid import UUID


class ValidationState(TypedDict, total=False):
    invoice_id: UUID
    po_id: UUID | None
    issue_codes: list[str]
    flow_outcome: str | None
    po_reroute_count: int
    open_issue_codes: list[str]
    decision: str | None
    invoice_status: str | None
    review_summary: dict[str, Any]


FLOW_OUTCOME_CONTINUE = "continue"
FLOW_OUTCOME_REROUTE = "reroute"
FLOW_OUTCOME_REJECT = "reject"
FLOW_OUTCOME_END = "end"

MAX_PO_REROUTE_COUNT = 2
