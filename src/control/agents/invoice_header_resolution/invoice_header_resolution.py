from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from src.control.agents.invoice_header_resolution.invoice_number_utils import (
    extract_invoice_number,
    generate_auto_invoice_number,
)
from src.control.validation_flow import build_validation_state
from src.core.exceptions.validation_exc import InvoiceNotFoundError
from src.data.models.postgres.enums import (
    IssueType,
    ValidationIssueStatus,
)
from src.data.repositories.invoice_header_resolution.invoice_email_repository import (
    InvoiceEmailRecord,
    InvoiceEmailRepository,
)
from src.data.repositories.invoice_header_resolution.invoice_repository import (
    InvoiceRecord,
    InvoiceRepository,
)
from src.data.repositories.shared.validation_issue_repository import (
    ValidationIssueCreate,
    ValidationIssueRepository,
)

logger = logging.getLogger(__name__)

CHECK_STAGE = "invoice_header_resolution"
MISSING_INVOICE_NUMBER = "MISSING_INVOICE_NUMBER"
WAIVED_INVOICE_NUMBER_DESCRIPTION = (
    "Original invoice number could not be recovered. "
    "A system-generated invoice identifier was assigned to allow processing."
)


class InvoiceHeaderResolutionAgent:
    def __init__(
        self,
        invoice_repo: InvoiceRepository,
        invoice_email_repo: InvoiceEmailRepository,
        validation_issue_repo: ValidationIssueRepository,
    ) -> None:
        self._invoice_repo = invoice_repo
        self._invoice_email_repo = invoice_email_repo
        self._validation_issue_repo = validation_issue_repo

    async def run(
        self,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        invoice_id = UUID(
            str(state["invoice_id"]),
        )
        issue_codes: list[str] = list(
            state.get(
                "issue_codes",
                [],
            ),
        )

        logger.info(
            "Starting invoice header resolution",
            extra={
                "invoice_id": str(invoice_id),
            },
        )

        invoice = await self._invoice_repo.get_invoice_by_id(
            invoice_id,
        )

        if invoice is None:
            raise InvoiceNotFoundError(
                invoice_id=invoice_id,
            )

        email = await self._invoice_email_repo.get_invoice_email(
            invoice_id,
        )

        issue_codes = await self._resolve_invoice_number(
            invoice=invoice,
            invoice_id=invoice_id,
            email=email,
            issue_codes=issue_codes,
        )

        await self._resolve_invoice_date(
            invoice=invoice,
            invoice_id=invoice_id,
            email=email,
        )

        logger.info(
            "Completed invoice header resolution",
            extra={
                "invoice_id": str(invoice_id),
                "issue_codes": issue_codes,
            },
        )

        return build_validation_state(
            invoice_id=invoice_id,
            po_id=state.get("po_id"),
            issue_codes=issue_codes,
        )

    async def _resolve_invoice_number(
        self,
        invoice: InvoiceRecord,
        invoice_id: UUID,
        email: InvoiceEmailRecord | None,
        issue_codes: list[str],
    ) -> list[str]:
        if invoice.invoice_number:
            logger.info(
                "Invoice number already present",
                extra={
                    "invoice_id": str(invoice_id),
                },
            )
            return issue_codes

        updated_codes = list(
            issue_codes,
        )

        if (
            MISSING_INVOICE_NUMBER
            not in updated_codes
        ):
            updated_codes.append(
                MISSING_INVOICE_NUMBER,
            )

        await self._validation_issue_repo.create_issue(
            invoice_id=invoice_id,
            issue=ValidationIssueCreate(
                check_stage=CHECK_STAGE,
                check_name="invoice_number_missing",
                field_name="invoice_number",
                issue_type=IssueType.MISSING,
                issue_code=MISSING_INVOICE_NUMBER,
                expected_value=None,
                actual_value=None,
                description=(
                    "Invoice number is missing on the invoice."
                ),
                status=ValidationIssueStatus.OPEN,
            ),
        )

        recovered_number = self._recover_invoice_number(
            email,
        )

        if recovered_number is not None:
            await self._invoice_repo.update_invoice_number(
                invoice_id,
                recovered_number,
            )
            await self._validation_issue_repo.mark_issue_resolved(
                invoice_id,
                MISSING_INVOICE_NUMBER,
            )
            logger.info(
                "Recovered invoice number from email",
                extra={
                    "invoice_id": str(invoice_id),
                    "invoice_number": recovered_number,
                },
            )
            return self._without_issue_code(
                updated_codes,
                MISSING_INVOICE_NUMBER,
            )

        auto_number = generate_auto_invoice_number(
            invoice_id,
        )

        await self._invoice_repo.update_invoice_number(
            invoice_id,
            auto_number,
        )
        await self._validation_issue_repo.mark_issue_waived(
            invoice_id,
            MISSING_INVOICE_NUMBER,
            description=WAIVED_INVOICE_NUMBER_DESCRIPTION,
        )

        logger.warning(
            "Generated system invoice number",
            extra={
                "invoice_id": str(invoice_id),
                "invoice_number": auto_number,
            },
        )

        return self._without_issue_code(
            updated_codes,
            MISSING_INVOICE_NUMBER,
        )

    async def _resolve_invoice_date(
        self,
        invoice: InvoiceRecord,
        invoice_id: UUID,
        email: InvoiceEmailRecord | None,
    ) -> None:
        if invoice.invoice_date is not None:
            logger.info(
                "Invoice date already present",
                extra={
                    "invoice_id": str(invoice_id),
                },
            )
            return

        if email is None or email.email_sent_date is None:
            logger.info(
                "No email date available for invoice date recovery",
                extra={
                    "invoice_id": str(invoice_id),
                },
            )
            return

        await self._invoice_repo.update_invoice_date(
            invoice_id,
            email.email_sent_date.date(),
        )

        logger.info(
            "Recovered invoice date from email sent date",
            extra={
                "invoice_id": str(invoice_id),
                "invoice_date": email.email_sent_date.date().isoformat(),
            },
        )

    @staticmethod
    def _recover_invoice_number(
        email: InvoiceEmailRecord | None,
    ) -> str | None:
        if email is None:
            return None

        recovered = extract_invoice_number(
            email.subject,
        )

        if recovered is not None:
            return recovered

        return extract_invoice_number(
            email.body_text,
        )

    @staticmethod
    def _without_issue_code(
        issue_codes: list[str],
        issue_code: str,
    ) -> list[str]:
        return [
            code
            for code in issue_codes
            if code != issue_code
        ]
