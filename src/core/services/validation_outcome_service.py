from __future__ import annotations

from uuid import UUID

from src.constants.validation_issue_codes import (
    AMBIGUOUS_ISSUE_CODES,
    DUPLICATE_ISSUE_CODES,
    PO_RECOVERED,
    RECOVERABLE_ISSUE_CODES,
    RECOVERY_CONFIRMATION_OPEN_CODES,
    STRUCTURAL_UNRESOLVED_ISSUE_CODES,
)
from src.data.models.postgres.enums import (
    InvoiceValidationOutcome,
    IssueType,
    POResolutionCandidateType,
    ValidationIssueStatus,
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
from src.data.repositories.shared.validation_issue_repository import (
    InvoiceIssueRecord,
    OpenIssueRecord,
    ValidationIssueRepository,
)


class ValidationOutcomeService:
    def __init__(
        self,
        invoice_repo: InvoiceRepository,
        resolution_group_repo: InvoicePOResolutionGroupRepository,
        allocation_candidate_repo: InvoiceLineAllocationCandidateRepository,
        validation_issue_repo: ValidationIssueRepository,
    ) -> None:
        self._invoice_repo = invoice_repo
        self._resolution_group_repo = resolution_group_repo
        self._allocation_candidate_repo = allocation_candidate_repo
        self._validation_issue_repo = validation_issue_repo

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
        open_issues = await self._validation_issue_repo.get_open_issues(
            invoice_id,
        )
        all_invoice_issues = (
            await self._validation_issue_repo.get_invoice_issues(
                invoice_id,
            )
        )

        open_codes = {
            issue.issue_code
            for issue in open_issues
        }
        relevant_codes = set(
            issue_codes,
        ) | open_codes

        if relevant_codes.intersection(
            DUPLICATE_ISSUE_CODES,
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

        structurally_ambiguous = (
            len(po_groups) > 1
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
        )

        if (
            relevant_codes.intersection(
                AMBIGUOUS_ISSUE_CODES,
            )
            or structurally_ambiguous
        ):
            return InvoiceValidationOutcome.AMBIGUOUS

        if not po_groups:
            return InvoiceValidationOutcome.UNRESOLVED

        if open_codes.intersection(
            STRUCTURAL_UNRESOLVED_ISSUE_CODES,
        ):
            return InvoiceValidationOutcome.UNRESOLVED

        blocking_open_issues = [
            issue
            for issue in open_issues
            if self._is_blocking_open_issue(
                issue,
            )
        ]

        if blocking_open_issues:
            return InvoiceValidationOutcome.UNRESOLVED

        has_recovery_signal = self._has_recovery_signal(
            po_groups=po_groups,
            allocation_groups=allocation_groups,
            open_codes=open_codes,
            invoice_issues=all_invoice_issues,
        )

        if open_codes:
            if open_codes.issubset(
                RECOVERY_CONFIRMATION_OPEN_CODES,
            ) and has_recovery_signal:
                return InvoiceValidationOutcome.RECOVERED

            warning_only_open = all(
                issue.issue_type == IssueType.WARNING
                for issue in open_issues
            )

            if warning_only_open and has_recovery_signal:
                return InvoiceValidationOutcome.RECOVERED

            return InvoiceValidationOutcome.UNRESOLVED

        if has_recovery_signal:
            return InvoiceValidationOutcome.RECOVERED

        if self._has_clean_resolved_structure(
            po_groups=po_groups,
            allocation_groups=allocation_groups,
        ):
            return InvoiceValidationOutcome.RESOLVED

        return InvoiceValidationOutcome.UNRESOLVED

    @staticmethod
    def _is_blocking_open_issue(
        issue: OpenIssueRecord,
    ) -> bool:
        if issue.issue_code in RECOVERY_CONFIRMATION_OPEN_CODES:
            return False

        if issue.issue_type == IssueType.WARNING:
            return False

        return True

    @staticmethod
    def _has_recovery_signal(
        *,
        po_groups: list[object],
        allocation_groups: list[object],
        open_codes: set[str],
        invoice_issues: list[InvoiceIssueRecord],
    ) -> bool:
        if PO_RECOVERED in open_codes:
            return True

        if any(
            group.candidate_type == POResolutionCandidateType.RECOVERED
            for group in po_groups
        ):
            return True

        if any(
            group.candidate_type == POResolutionCandidateType.RECOVERED
            for group in allocation_groups
        ):
            return True

        return any(
            issue.issue_code in RECOVERABLE_ISSUE_CODES
            and issue.status
            in (
                ValidationIssueStatus.RESOLVED,
                ValidationIssueStatus.WAIVED,
            )
            for issue in invoice_issues
        )

    @staticmethod
    def _has_clean_resolved_structure(
        *,
        po_groups: list[object],
        allocation_groups: list[object],
    ) -> bool:
        if (
            len(po_groups) != 1
            or po_groups[0].candidate_type
            != POResolutionCandidateType.RESOLVED
        ):
            return False

        if len(allocation_groups) != 1:
            return False

        return allocation_groups[0].candidate_type in (
            POResolutionCandidateType.RESOLVED,
            POResolutionCandidateType.RECOVERED,
        )
