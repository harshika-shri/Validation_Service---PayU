from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal, cast

from langgraph.graph import END, START, StateGraph

from src.control.agents.amount_validation.amount_validation import (
    AmountValidationAgent,
)
from src.control.agents.company_resolution.company_resolution import (
    BuyerCompanyValidationAgent,
)
from src.control.agents.duplicate_detection.duplicate_detection import (
    DuplicateDetectionAgent,
)
from src.control.agents.final_decision.final_decision import (
    FinalDecisionAgent,
)
from src.control.agents.invoice_header_resolution.invoice_header_resolution import (
    InvoiceHeaderResolutionAgent,
)
from src.control.agents.line_item_validation.line_item_validation import (
    LineItemValidationAgent,
)
from src.control.agents.po_resolution.po_resolution import (
    POResolutionAgent,
)
from src.control.agents.review_summary_generation.review_summary_generation import (
    ReviewSummaryGenerationAgent,
)
from src.control.agents.vendor_resolution.vendor_resolution import (
    VendorResolutionAgent,
)
from src.control.graph.validation_state import (
    FLOW_OUTCOME_CONTINUE,
    FLOW_OUTCOME_END,
    FLOW_OUTCOME_REJECT,
    FLOW_OUTCOME_REROUTE,
    MAX_PO_REROUTE_COUNT,
    ValidationState,
)
from src.control.validation_flow import (
    MISSING_PO_COVERAGE,
    PO_UNRESOLVED,
)
from src.data.models.postgres.enums import (
    IssueType,
    ValidationFlowOutcome,
    ValidationIssueStatus,
)
from src.data.repositories.shared.validation_issue_repository import (
    ValidationIssueCreate,
    ValidationIssueRepository,
)

logger = logging.getLogger(__name__)

CHECK_STAGE = "validation_graph"


@dataclass(frozen=True, slots=True)
class ValidationAgents:
    invoice_header_resolution: InvoiceHeaderResolutionAgent
    company_resolution: BuyerCompanyValidationAgent
    vendor_resolution: VendorResolutionAgent
    po_resolution: POResolutionAgent
    line_item_validation: LineItemValidationAgent
    amount_validation: AmountValidationAgent
    duplicate_detection: DuplicateDetectionAgent
    final_decision: FinalDecisionAgent
    review_summary_generation: ReviewSummaryGenerationAgent


def build_validation_graph(
    agents: ValidationAgents,
    validation_issue_repo: ValidationIssueRepository,
):
    graph = StateGraph(
        ValidationState,
    )

    async def invoice_header_resolution_node(
        state: ValidationState,
    ) -> ValidationState:
        return await _run_agent_node(
            node_name="invoice_header_resolution",
            state=state,
            runner=agents.invoice_header_resolution.run,
        )

    async def company_resolution_node(
        state: ValidationState,
    ) -> ValidationState:
        return await _run_agent_node(
            node_name="company_resolution",
            state=state,
            runner=agents.company_resolution.run,
        )

    async def vendor_resolution_node(
        state: ValidationState,
    ) -> ValidationState:
        return await _run_agent_node(
            node_name="vendor_resolution",
            state=state,
            runner=agents.vendor_resolution.run,
        )

    async def po_resolution_node(
        state: ValidationState,
    ) -> ValidationState:
        return await _run_agent_node(
            node_name="po_resolution",
            state=state,
            runner=agents.po_resolution.run,
        )

    async def line_item_validation_node(
        state: ValidationState,
    ) -> ValidationState:
        return await _run_agent_node(
            node_name="line_item_validation",
            state=state,
            runner=agents.line_item_validation.run,
        )

    async def amount_validation_node(
        state: ValidationState,
    ) -> ValidationState:
        return await _run_agent_node(
            node_name="amount_validation",
            state=state,
            runner=agents.amount_validation.run,
        )

    async def duplicate_detection_node(
        state: ValidationState,
    ) -> ValidationState:
        return await _run_agent_node(
            node_name="duplicate_detection",
            state=state,
            runner=agents.duplicate_detection.run,
        )

    async def final_decision_node(
        state: ValidationState,
    ) -> ValidationState:
        result = await _run_agent_node(
            node_name="final_decision",
            state=state,
            runner=agents.final_decision.run,
        )

        logger.info(
            "Final Decision",
            extra={
                "invoice_id": str(
                    result["invoice_id"],
                ),
                "decision": result.get(
                    "decision",
                ),
                "invoice_status": result.get(
                    "invoice_status",
                ),
            },
        )

        return result

    async def review_summary_generation_node(
        state: ValidationState,
    ) -> ValidationState:
        result = await _run_agent_node(
            node_name="review_summary_generation",
            state=state,
            runner=agents.review_summary_generation.run,
        )

        return {
            **result,
            "flow_outcome": FLOW_OUTCOME_END,
        }

    async def prepare_po_reroute_node(
        state: ValidationState,
    ) -> ValidationState:
        reroute_count = state.get(
            "po_reroute_count",
            0,
        ) + 1

        logger.info(
            "Re-route Triggered",
            extra={
                "invoice_id": str(
                    state["invoice_id"],
                ),
                "issue_code": MISSING_PO_COVERAGE,
                "po_reroute_count": reroute_count,
            },
        )

        return {
            **state,
            "po_reroute_count": reroute_count,
        }

    async def handle_reroute_limit_node(
        state: ValidationState,
    ) -> ValidationState:
        invoice_id = state["invoice_id"]
        issue_codes = list(
            state.get(
                "issue_codes",
                [],
            ),
        )

        logger.warning(
            "Re-route limit exceeded",
            extra={
                "invoice_id": str(
                    invoice_id,
                ),
                "po_reroute_count": state.get(
                    "po_reroute_count",
                    0,
                ),
                "max_po_reroute_count": MAX_PO_REROUTE_COUNT,
            },
        )

        if PO_UNRESOLVED not in issue_codes:
            await validation_issue_repo.create_issue(
                invoice_id=invoice_id,
                issue=ValidationIssueCreate(
                    check_stage=CHECK_STAGE,
                    check_name="po_reroute_limit",
                    field_name="po_id",
                    issue_type=IssueType.MISSING,
                    issue_code=PO_UNRESOLVED,
                    expected_value=None,
                    actual_value=None,
                    description=(
                        "PO re-route limit exceeded while resolving "
                        "missing purchase order coverage."
                    ),
                    status=ValidationIssueStatus.OPEN,
                ),
            )
            issue_codes.append(
                PO_UNRESOLVED,
            )

            logger.info(
                "Issues Added",
                extra={
                    "invoice_id": str(
                        invoice_id,
                    ),
                    "node": "handle_reroute_limit",
                    "issue_codes": [
                        PO_UNRESOLVED,
                    ],
                },
            )

        logger.info(
            "Hard Stop Triggered",
            extra={
                "invoice_id": str(
                    invoice_id,
                ),
                "node": "handle_reroute_limit",
                "flow_outcome": FLOW_OUTCOME_REJECT,
            },
        )

        return {
            **state,
            "issue_codes": issue_codes,
            "flow_outcome": ValidationFlowOutcome.HARD_STOP.value,
        }

    graph.add_node(
        "invoice_header_resolution",
        invoice_header_resolution_node,
    )
    graph.add_node(
        "company_resolution",
        company_resolution_node,
    )
    graph.add_node(
        "vendor_resolution",
        vendor_resolution_node,
    )
    graph.add_node(
        "po_resolution",
        po_resolution_node,
    )
    graph.add_node(
        "line_item_validation",
        line_item_validation_node,
    )
    graph.add_node(
        "amount_validation",
        amount_validation_node,
    )
    graph.add_node(
        "duplicate_detection",
        duplicate_detection_node,
    )
    graph.add_node(
        "final_decision",
        final_decision_node,
    )
    graph.add_node(
        "review_summary_generation",
        review_summary_generation_node,
    )
    graph.add_node(
        "prepare_po_reroute",
        prepare_po_reroute_node,
    )
    graph.add_node(
        "handle_reroute_limit",
        handle_reroute_limit_node,
    )

    graph.add_edge(
        START,
        "invoice_header_resolution",
    )
    graph.add_edge(
        "invoice_header_resolution",
        "company_resolution",
    )
    graph.add_edge(
        "company_resolution",
        "vendor_resolution",
    )
    graph.add_conditional_edges(
        "vendor_resolution",
        _route_after_vendor,
        {
            "po_resolution": "po_resolution",
            "final_decision": "final_decision",
        },
    )
    graph.add_conditional_edges(
        "po_resolution",
        _route_after_po_resolution,
        {
            "line_item_validation": "line_item_validation",
            "final_decision": "final_decision",
        },
    )
    graph.add_conditional_edges(
        "line_item_validation",
        _route_after_line_item_validation,
        {
            "amount_validation": "amount_validation",
            "prepare_po_reroute": "prepare_po_reroute",
            "handle_reroute_limit": "handle_reroute_limit",
            "final_decision": "final_decision",
        },
    )
    graph.add_edge(
        "prepare_po_reroute",
        "po_resolution",
    )
    graph.add_edge(
        "handle_reroute_limit",
        "final_decision",
    )
    graph.add_conditional_edges(
        "amount_validation",
        _route_after_amount_validation,
        {
            "duplicate_detection": "duplicate_detection",
            "final_decision": "final_decision",
        },
    )
    graph.add_conditional_edges(
        "duplicate_detection",
        _route_after_duplicate_detection,
        {
            "final_decision": "final_decision",
        },
    )
    graph.add_edge(
        "final_decision",
        "review_summary_generation",
    )
    graph.add_edge(
        "review_summary_generation",
        END,
    )

    return graph.compile()


async def _run_agent_node(
    *,
    node_name: str,
    state: ValidationState,
    runner: Any,
) -> ValidationState:
    invoice_id = state["invoice_id"]
    issue_codes_before = list(
        state.get(
            "issue_codes",
            [],
        ),
    )

    logger.info(
        "Node Start",
        extra={
            "node": node_name,
            "invoice_id": str(
                invoice_id,
            ),
            "flow_outcome": _normalize_flow_outcome(
                state.get(
                    "flow_outcome",
                ),
            ),
        },
    )

    result = await runner(
        dict(
            state,
        ),
    )
    updated_state = cast_validation_state(
        result,
    )
    issue_codes_after = list(
        updated_state.get(
            "issue_codes",
            [],
        ),
    )
    added_issues = sorted(
        set(
            issue_codes_after,
        )
        - set(
            issue_codes_before,
        ),
    )

    if added_issues:
        logger.info(
            "Issues Added",
            extra={
                "node": node_name,
                "invoice_id": str(
                    invoice_id,
                ),
                "issue_codes": added_issues,
            },
        )

    logger.info(
        "Node End",
        extra={
            "node": node_name,
            "invoice_id": str(
                invoice_id,
            ),
            "flow_outcome": _normalize_flow_outcome(
                updated_state.get(
                    "flow_outcome",
                ),
            ),
        },
    )

    return updated_state


def cast_validation_state(
    state: dict[str, Any],
) -> ValidationState:
    return cast(
        ValidationState,
        {
            "invoice_id": state["invoice_id"],
            "po_id": state.get(
                "po_id",
            ),
            "issue_codes": list(
                state.get(
                    "issue_codes",
                    [],
                ),
            ),
            "flow_outcome": state.get(
                "flow_outcome",
            ),
            "po_reroute_count": int(
                state.get(
                    "po_reroute_count",
                    0,
                ),
            ),
            "open_issue_codes": list(
                state.get(
                    "open_issue_codes",
                    [],
                ),
            ),
            "decision": state.get(
                "decision",
            ),
            "invoice_status": state.get(
                "invoice_status",
            ),
            "review_summary": state.get(
                "review_summary",
            ),
        },
    )


def _normalize_flow_outcome(
    flow_outcome: str | None,
) -> str:
    if flow_outcome in {
        ValidationFlowOutcome.HARD_STOP.value,
        FLOW_OUTCOME_REJECT,
        "REJECT",
    }:
        return FLOW_OUTCOME_REJECT

    if flow_outcome in {
        ValidationFlowOutcome.REROUTE.value,
        FLOW_OUTCOME_REROUTE,
        "REROUTE",
    }:
        return FLOW_OUTCOME_REROUTE

    if flow_outcome in {
        FLOW_OUTCOME_END,
        "END",
    }:
        return FLOW_OUTCOME_END

    return FLOW_OUTCOME_CONTINUE


def _is_reject(
    state: ValidationState,
) -> bool:
    return (
        _normalize_flow_outcome(
            state.get(
                "flow_outcome",
            ),
        )
        == FLOW_OUTCOME_REJECT
    )


def _is_reroute(
    state: ValidationState,
) -> bool:
    return (
        _normalize_flow_outcome(
            state.get(
                "flow_outcome",
            ),
        )
        == FLOW_OUTCOME_REROUTE
    )


def _route_after_vendor(
    state: ValidationState,
) -> Literal["po_resolution", "final_decision"]:
    if _is_reject(
        state,
    ):
        logger.info(
            "Hard Stop Triggered",
            extra={
                "invoice_id": str(
                    state["invoice_id"],
                ),
                "node": "vendor_resolution",
            },
        )
        return "final_decision"

    return "po_resolution"


def _route_after_po_resolution(
    state: ValidationState,
) -> Literal["line_item_validation", "final_decision"]:
    if _is_reject(
        state,
    ):
        logger.info(
            "Hard Stop Triggered",
            extra={
                "invoice_id": str(
                    state["invoice_id"],
                ),
                "node": "po_resolution",
            },
        )
        return "final_decision"

    return "line_item_validation"


def _route_after_line_item_validation(
    state: ValidationState,
) -> Literal[
    "amount_validation",
    "prepare_po_reroute",
    "handle_reroute_limit",
    "final_decision",
]:
    if _is_reject(
        state,
    ):
        logger.info(
            "Hard Stop Triggered",
            extra={
                "invoice_id": str(
                    state["invoice_id"],
                ),
                "node": "line_item_validation",
            },
        )
        return "final_decision"

    if (
        _is_reroute(
            state,
        )
        and MISSING_PO_COVERAGE
        in state.get(
            "issue_codes",
            [],
        )
    ):
        reroute_count = state.get(
            "po_reroute_count",
            0,
        )

        if reroute_count >= MAX_PO_REROUTE_COUNT:
            return "handle_reroute_limit"

        return "prepare_po_reroute"

    return "amount_validation"


def _route_after_amount_validation(
    state: ValidationState,
) -> Literal["duplicate_detection", "final_decision"]:
    if _is_reject(
        state,
    ):
        logger.info(
            "Hard Stop Triggered",
            extra={
                "invoice_id": str(
                    state["invoice_id"],
                ),
                "node": "amount_validation",
            },
        )
        return "final_decision"

    return "duplicate_detection"


def _route_after_duplicate_detection(
    state: ValidationState,
) -> Literal["final_decision"]:
    if _is_reject(
        state,
    ):
        logger.info(
            "Hard Stop Triggered",
            extra={
                "invoice_id": str(
                    state["invoice_id"],
                ),
                "node": "duplicate_detection",
            },
        )

    return "final_decision"
