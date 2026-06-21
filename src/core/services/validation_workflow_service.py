from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.control.agents.amount_validation import (
    AmountValidationAgent,
)
from src.control.agents.buyer_company_validation import (
    BuyerCompanyValidationAgent,
)
from src.control.agents.duplicate_detection import (
    DuplicateDetectionAgent,
)
from src.control.agents.final_decision import (
    FinalDecisionAgent,
)
from src.control.agents.invoice_header_resolution import (
    InvoiceHeaderResolutionAgent,
)
from src.control.agents.line_item_validation import (
    LineItemValidationAgent,
)
from src.control.agents.po_resolution import (
    POResolutionAgent,
)
from src.control.agents.review_summary_generation import (
    ReviewSummaryGenerationAgent,
)
from src.control.agents.vendor_resolution import (
    VendorResolutionAgent,
)
from src.control.graph.validation_graph import (
    ValidationAgents,
    build_validation_graph,
)
from src.control.graph.validation_state import (
    ValidationState,
)
from src.core.services.allocation_lifecycle_service import (
    AllocationLifecycleService,
)
from src.core.services.validation_state_mapper import (
    validation_state_to_schema,
)
from src.data.models.postgres.enums import ValidationFlowOutcome
from src.data.repositories.company_repository import (
    CompanyRepository,
)
from src.data.repositories.duplicate_detection_repository import (
    DuplicateDetectionRepository,
)
from src.data.repositories.invoice_amount_repository import (
    InvoiceAmountRepository,
)
from src.data.repositories.invoice_email_repository import (
    InvoiceEmailRepository,
)
from src.data.repositories.invoice_extracted_vendor_repository import (
    InvoiceExtractedVendorRepository,
)
from src.data.repositories.invoice_line_amount_repository import (
    InvoiceLineAmountRepository,
)
from src.data.repositories.invoice_line_item_repository import (
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
)
from src.data.repositories.invoice_repository import (
    InvoiceRepository,
)
from src.data.repositories.invoice_review_summary_repository import (
    InvoiceReviewSummaryRepository,
)
from src.data.repositories.issue_decision_rules_repository import (
    IssueDecisionRulesRepository,
)
from src.data.repositories.po_line_item_repository import (
    POLineItemRepository,
)
from src.data.repositories.po_line_quantity_repository import (
    POLineQuantityRepository,
)
from src.data.repositories.purchase_order_repository import (
    PurchaseOrderRepository,
)
from src.data.repositories.validation_issue_repository import (
    ValidationIssueRepository,
)
from src.data.repositories.vendor_repository import (
    VendorRepository,
)
from src.schemas.validation_state_schema import (
    ValidationStateSchema,
)


class ValidationWorkflowService:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def run_invoice_validation(
        self,
        invoice_id: UUID,
    ) -> ValidationStateSchema:
        agents, validation_issue_repo = self._build_agents()
        graph = build_validation_graph(
            agents=agents,
            validation_issue_repo=validation_issue_repo,
        )

        initial_state: ValidationState = {
            "invoice_id": invoice_id,
            "po_id": None,
            "issue_codes": [],
            "flow_outcome": ValidationFlowOutcome.CONTINUE.value,
            "po_reroute_count": 0,
        }

        final_state = await graph.ainvoke(
            initial_state,
        )

        return validation_state_to_schema(
            dict(
                final_state,
            ),
        )

    def _build_agents(
        self,
    ) -> tuple[ValidationAgents, ValidationIssueRepository]:
        invoice_repo = InvoiceRepository(
            self._session,
        )
        invoice_email_repo = InvoiceEmailRepository(
            self._session,
        )
        validation_issue_repo = ValidationIssueRepository(
            self._session,
        )
        company_repo = CompanyRepository(
            self._session,
        )
        extracted_vendor_repo = InvoiceExtractedVendorRepository(
            self._session,
        )
        vendor_repo = VendorRepository(
            self._session,
        )
        invoice_po_repo = InvoicePOResolutionRepository(
            self._session,
        )
        invoice_line_item_repo = InvoiceLineItemRepository(
            self._session,
        )
        purchase_order_repo = PurchaseOrderRepository(
            self._session,
        )
        po_line_item_repo = POLineItemRepository(
            self._session,
        )
        po_line_quantity_repo = POLineQuantityRepository(
            self._session,
        )
        invoice_po_mapping_repo = InvoicePOMappingRepository(
            self._session,
        )
        allocation_repo = InvoiceLinePOAllocationRepository(
            self._session,
        )
        invoice_amount_repo = InvoiceAmountRepository(
            self._session,
        )
        invoice_line_amount_repo = InvoiceLineAmountRepository(
            self._session,
        )
        duplicate_detection_repo = DuplicateDetectionRepository(
            self._session,
        )
        decision_rules_repo = IssueDecisionRulesRepository(
            self._session,
        )
        review_summary_repo = InvoiceReviewSummaryRepository(
            self._session,
        )
        allocation_lifecycle_service = AllocationLifecycleService(
            self._session,
        )

        agents = ValidationAgents(
            invoice_header_resolution=InvoiceHeaderResolutionAgent(
                invoice_repo=invoice_repo,
                invoice_email_repo=invoice_email_repo,
                validation_issue_repo=validation_issue_repo,
            ),
            company_resolution=BuyerCompanyValidationAgent(
                company_repo=company_repo,
                invoice_repo=invoice_repo,
                validation_issue_repo=validation_issue_repo,
            ),
            vendor_resolution=VendorResolutionAgent(
                extracted_vendor_repo=extracted_vendor_repo,
                vendor_repo=vendor_repo,
                validation_issue_repo=validation_issue_repo,
            ),
            po_resolution=POResolutionAgent(
                invoice_po_repo=invoice_po_repo,
                invoice_line_item_repo=invoice_line_item_repo,
                extracted_vendor_repo=extracted_vendor_repo,
                purchase_order_repo=purchase_order_repo,
                po_line_item_repo=po_line_item_repo,
                po_line_quantity_repo=po_line_quantity_repo,
                invoice_po_mapping_repo=invoice_po_mapping_repo,
                allocation_repo=allocation_repo,
                validation_issue_repo=validation_issue_repo,
            ),
            line_item_validation=LineItemValidationAgent(
                invoice_line_item_repo=invoice_line_item_repo,
                invoice_po_mapping_repo=invoice_po_mapping_repo,
                po_line_item_repo=po_line_item_repo,
                po_line_quantity_repo=po_line_quantity_repo,
                allocation_repo=allocation_repo,
                extracted_vendor_repo=extracted_vendor_repo,
                purchase_order_repo=purchase_order_repo,
                validation_issue_repo=validation_issue_repo,
            ),
            amount_validation=AmountValidationAgent(
                invoice_amount_repo=invoice_amount_repo,
                invoice_line_amount_repo=invoice_line_amount_repo,
                allocation_repo=allocation_repo,
                invoice_po_mapping_repo=invoice_po_mapping_repo,
                po_line_item_repo=po_line_item_repo,
                purchase_order_repo=purchase_order_repo,
                validation_issue_repo=validation_issue_repo,
            ),
            duplicate_detection=DuplicateDetectionAgent(
                duplicate_repo=duplicate_detection_repo,
                extracted_vendor_repo=extracted_vendor_repo,
                validation_issue_repo=validation_issue_repo,
            ),
            final_decision=FinalDecisionAgent(
                validation_issue_repo=validation_issue_repo,
                decision_rules_repo=decision_rules_repo,
                invoice_repo=invoice_repo,
                invoice_po_mapping_repo=invoice_po_mapping_repo,
                allocation_lifecycle_service=allocation_lifecycle_service,
            ),
            review_summary_generation=ReviewSummaryGenerationAgent(
                invoice_repo=invoice_repo,
                validation_issue_repo=validation_issue_repo,
                review_summary_repo=review_summary_repo,
                invoice_po_mapping_repo=invoice_po_mapping_repo,
                purchase_order_repo=purchase_order_repo,
            ),
        )

        return agents, validation_issue_repo
