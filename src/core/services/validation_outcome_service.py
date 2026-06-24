from __future__ import annotations

from uuid import UUID

from src.constants.validation_issue_codes import (
    DUPLICATE_INVOICE_NUMBER,
    POTENTIAL_DUPLICATE_INVOICE,
)
from src.control.validation_flow import (
    AMBIGUOUS_LINE_MATCH,
    MISSING_PO_COVERAGE,
    PO_AMBIGUOUS,
    PO_RESOLUTION_BLOCKED,
    PO_UNRESOLVED,
    UNMATCHED_LINE_ITEM,
)
from src.data.models.postgres.enums import (
    InvoiceValidationOutcome,
    POResolutionCandidateType,
)
from src.data.repositories.invoice_header_resolution.invoice_repository import (
    InvoiceRepository,
)
from src.data.repositories.po_resolution.invoice_line_allocation_candidate_repository import (
    InvoiceLineAllocationCandidateRepository,
)
from src.data.repositories.po_resolution.invoice_po_resolution_group_repository import (
    InvoicePOResolutionGroupRepository,
)

_DUPLICATE_ISSUE_CODES = frozenset(
    {
        DUPLICATE_INVOICE_NUMBER,
        POTENTIAL_DUPLICATE_INVOICE,
    },
)

_AMBIGUOUS_ISSUE_CODES = frozenset(
    {
        PO_AMBIGUOUS,
        AMBIGUOUS_LINE_MATCH,
    },
)

_UNRESOLVED_ISSUE_CODES = frozenset(
    {
        PO_UNRESOLVED,
        PO_RESOLUTION_BLOCKED,
        UNMATCHED_LINE_ITEM,
        MISSING_PO_COVERAGE,
    },
)


class ValidationOutcomeService:
    def __init__(
        self,
        invoice_repo: InvoiceRepository,
        resolution_group_repo: InvoicePOResolutionGroupRepository,
        allocation_candidate_repo: InvoiceLineAllocationCandidateRepository,
    ) -> None:
        self._invoice_repo = invoice_repo
        self._resolution_group_repo = resolution_group_repo
        self._allocation_candidate_repo = allocation_candidate_repo

    async def resolve_and_persist(
        self,
        invoice_id: UUID,
        issue_codes: list[str],
    ) -> InvoiceValidationOutcome:
        outcome = await self._resolve(
            invoice_id=invoice_id,
            issue_codes=issue_codes,
        )

        await self._invoice_repo.update_validation_outcome(
            invoice_id=invoice_id,
            validation_outcome=outcome,
        )

        return outcome

    async def _resolve(
        self,
        invoice_id: UUID,
        issue_codes: list[str],
    ) -> InvoiceValidationOutcome:
        codes = set(
            issue_codes,
        )

        if codes.intersection(
            _DUPLICATE_ISSUE_CODES,
        ):
            return InvoiceValidationOutcome.DUPLICATE

        po_groups = (
            await self._resolution_group_repo.get_groups_for_invoice(
                invoice_id,
            )
        )
        allocation_groups = (
            await self._allocation_candidate_repo.get_groups_for_invoice(
                invoice_id,
            )
        )

        if (
            codes.intersection(
                _AMBIGUOUS_ISSUE_CODES,
            )
            or len(po_groups) > 1
            or any(
                group.candidate_type
                == POResolutionCandidateType.AMBIGUOUS
                for group in po_groups
            )
            or len(allocation_groups) > 1
            or any(
                group.candidate_type
                == POResolutionCandidateType.AMBIGUOUS
                for group in allocation_groups
            )
        ):
            return InvoiceValidationOutcome.AMBIGUOUS

        if (
            not po_groups
            or codes.intersection(
                _UNRESOLVED_ISSUE_CODES,
            )
        ):
            return InvoiceValidationOutcome.UNRESOLVED

        if (
            any(
                group.candidate_type
                == POResolutionCandidateType.RECOVERED
                for group in po_groups
            )
            or any(
                group.candidate_type
                == POResolutionCandidateType.RECOVERED
                for group in allocation_groups
            )
            or "PO_RECOVERED" in codes
        ):
            return InvoiceValidationOutcome.RECOVERED

        if (
            len(po_groups) == 1
            and po_groups[0].candidate_type
            == POResolutionCandidateType.RESOLVED
            and len(allocation_groups) == 1
            and allocation_groups[0].candidate_type
            in (
                POResolutionCandidateType.RESOLVED,
                POResolutionCandidateType.RECOVERED,
            )
        ):
            if (
                allocation_groups[0].candidate_type
                == POResolutionCandidateType.RECOVERED
            ):
                return InvoiceValidationOutcome.RECOVERED

            return InvoiceValidationOutcome.RESOLVED

        return InvoiceValidationOutcome.UNRESOLVED
