from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select, update

from src.data.models.postgres.enums import (
    IssueType,
    ValidationIssueStatus,
)
from src.data.models.postgres.invoice_validation_issues import (
    InvoiceValidationIssue,
)
from src.data.repositories.base_repo import BaseRepository

from src.constants.validation_issue_codes import RECOVERABLE_ISSUE_CODES

_ACTIVE_ISSUE_STATUSES = (
    ValidationIssueStatus.OPEN,
    ValidationIssueStatus.PENDING_REVIEW,
)

RECOVERABLE_ISSUE_CODES = RECOVERABLE_ISSUE_CODES


@dataclass(frozen=True, slots=True)
class ValidationIssueCreate:
    check_stage: str
    check_name: str
    field_name: str | None
    issue_type: IssueType
    description: str
    status: ValidationIssueStatus
    issue_code: str | None = None
    expected_value: str | None = None
    actual_value: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class OpenIssueRecord:
    issue_code: str
    issue_type: IssueType


@dataclass(frozen=True, slots=True)
class InvoiceIssueRecord:
    issue_code: str
    issue_type: IssueType
    status: ValidationIssueStatus


@dataclass(frozen=True, slots=True)
class InvoiceIssueDetailRecord:
    issue_code: str
    issue_type: IssueType
    status: ValidationIssueStatus
    metadata: dict[str, Any] | None


class ValidationIssueRepository(BaseRepository):
    async def create_issue(
        self,
        invoice_id: UUID,
        issue: ValidationIssueCreate,
    ) -> InvoiceValidationIssue | None:
        if (
            issue.issue_code is not None
            and await self.has_open_issue(
                invoice_id,
                issue.issue_code,
            )
        ):
            return None

        metadata = dict(
            issue.metadata or {},
        )

        if issue.issue_code is not None:
            metadata["issue_code"] = issue.issue_code

        validation_issue = InvoiceValidationIssue(
            invoice_id=invoice_id,
            check_stage=issue.check_stage,
            check_name=issue.check_name,
            field_name=issue.field_name,
            issue_type=issue.issue_type,
            expected_value=issue.expected_value,
            actual_value=issue.actual_value,
            description=issue.description,
            status=issue.status,
            issue_metadata=metadata or None,
        )

        self.session.add(
            validation_issue,
        )
        await self.session.flush()

        return validation_issue

    async def has_open_issue(
        self,
        invoice_id: UUID,
        issue_code: str,
    ) -> bool:
        stmt = (
            select(
                InvoiceValidationIssue.id,
            )
            .where(
                InvoiceValidationIssue.invoice_id == invoice_id,
                InvoiceValidationIssue.status.in_(
                    _ACTIVE_ISSUE_STATUSES,
                ),
                InvoiceValidationIssue.issue_metadata[
                    "issue_code"
                ].as_string()
                == issue_code,
            )
            .limit(
                1,
            )
        )

        result = await self.execute(
            stmt,
        )

        return result.scalar_one_or_none() is not None

    async def mark_issue_resolved(
        self,
        invoice_id: UUID,
        issue_code: str,
    ) -> int:
        stmt = (
            update(
                InvoiceValidationIssue,
            )
            .where(
                InvoiceValidationIssue.invoice_id == invoice_id,
                InvoiceValidationIssue.status.in_(
                    _ACTIVE_ISSUE_STATUSES,
                ),
                InvoiceValidationIssue.issue_metadata[
                    "issue_code"
                ].as_string()
                == issue_code,
            )
            .values(
                status=ValidationIssueStatus.RESOLVED,
            )
        )

        result = await self.execute(
            stmt,
        )

        return result.rowcount or 0

    async def mark_issue_waived(
        self,
        invoice_id: UUID,
        issue_code: str,
        description: str | None = None,
    ) -> int:
        values: dict[str, Any] = {
            "status": ValidationIssueStatus.WAIVED,
        }

        if description is not None:
            values["description"] = description

        stmt = (
            update(
                InvoiceValidationIssue,
            )
            .where(
                InvoiceValidationIssue.invoice_id == invoice_id,
                InvoiceValidationIssue.status.in_(
                    _ACTIVE_ISSUE_STATUSES,
                ),
                InvoiceValidationIssue.issue_metadata[
                    "issue_code"
                ].as_string()
                == issue_code,
            )
            .values(
                **values,
            )
        )

        result = await self.execute(
            stmt,
        )

        return result.rowcount or 0

    async def get_open_issues(
        self,
        invoice_id: UUID,
    ) -> list[OpenIssueRecord]:
        invoice_issues = await self.get_invoice_issues(
            invoice_id,
        )

        return [
            OpenIssueRecord(
                issue_code=issue.issue_code,
                issue_type=issue.issue_type,
            )
            for issue in invoice_issues
            if issue.status in _ACTIVE_ISSUE_STATUSES
        ]

    async def get_invoice_issues(
        self,
        invoice_id: UUID,
    ) -> list[InvoiceIssueRecord]:
        stmt = (
            select(
                InvoiceValidationIssue.issue_type,
                InvoiceValidationIssue.status,
                InvoiceValidationIssue.issue_metadata,
            )
            .where(
                InvoiceValidationIssue.invoice_id == invoice_id,
            )
        )

        result = await self.execute(
            stmt,
        )

        invoice_issues: list[InvoiceIssueRecord] = []

        for row in result.all():
            metadata = row.issue_metadata or {}
            issue_code = metadata.get(
                "issue_code",
            )

            if not issue_code:
                continue

            invoice_issues.append(
                InvoiceIssueRecord(
                    issue_code=str(
                        issue_code,
                    ),
                    issue_type=row.issue_type,
                    status=row.status,
                ),
            )

        return invoice_issues

    async def get_invoice_issue_details(
        self,
        invoice_id: UUID,
    ) -> list[InvoiceIssueDetailRecord]:
        stmt = (
            select(
                InvoiceValidationIssue.issue_type,
                InvoiceValidationIssue.status,
                InvoiceValidationIssue.issue_metadata,
            )
            .where(
                InvoiceValidationIssue.invoice_id == invoice_id,
            )
        )

        result = await self.execute(
            stmt,
        )

        invoice_issues: list[InvoiceIssueDetailRecord] = []

        for row in result.all():
            metadata = row.issue_metadata or {}
            issue_code = metadata.get(
                "issue_code",
            )

            if not issue_code:
                continue

            invoice_issues.append(
                InvoiceIssueDetailRecord(
                    issue_code=str(
                        issue_code,
                    ),
                    issue_type=row.issue_type,
                    status=row.status,
                    metadata=metadata,
                ),
            )

        return invoice_issues

    async def get_open_issue_codes(
        self,
        invoice_id: UUID,
    ) -> list[str]:
        open_issues = await self.get_open_issues(
            invoice_id,
        )

        return [
            issue.issue_code
            for issue in open_issues
        ]
