from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.control.validation_flow import build_validation_state
from src.core.exceptions.llm_exc import LLMServiceError
from src.core.exceptions.validation_exc import InvoiceNotFoundError
from src.data.models.postgres.enums import (
    IssueType,
    ValidationIssueStatus,
)
from src.data.repositories.company_resolution.company_repository import (
    CompanyRecord,
    CompanyRepository,
)
from src.data.repositories.invoice_header_resolution.invoice_repository import (
    BuyerCompanyExtractedRecord,
    InvoiceRepository,
)
from src.data.repositories.shared.validation_issue_repository import (
    ValidationIssueCreate,
    ValidationIssueRepository,
)
from src.utils.company_matching_utils import (
    has_text,
    normalize_address,
    normalize_company_name_for_exact_match,
    normalize_email,
    normalize_gstin,
    normalize_pan,
    normalize_phone,
)
from src.utils.llm_client import (
    compare_addresses_semantically,
    compare_company_names_semantically,
)

logger = logging.getLogger(__name__)

CHECK_STAGE = "buyer_company_validation"

COMPANY_DETAILS_MISSING = "COMPANY_DETAILS_MISSING"
MISSING_COMPANY_NAME = "MISSING_COMPANY_NAME"
MISSING_COMPANY_GSTIN = "MISSING_COMPANY_GSTIN"
MISSING_COMPANY_ADDRESS = "MISSING_COMPANY_ADDRESS"
COMPANY_NAME_MISMATCH = "COMPANY_NAME_MISMATCH"
COMPANY_GSTIN_MISMATCH = "COMPANY_GSTIN_MISMATCH"
COMPANY_PAN_MISMATCH = "COMPANY_PAN_MISMATCH"
COMPANY_ADDRESS_MISMATCH = "COMPANY_ADDRESS_MISMATCH"
COMPANY_SHIPPING_ADDRESS_MISMATCH = "COMPANY_SHIPPING_ADDRESS_MISMATCH"
COMPANY_EMAIL_MISMATCH = "COMPANY_EMAIL_MISMATCH"
COMPANY_PHONE_MISMATCH = "COMPANY_PHONE_MISMATCH"
COMPANY_BANK_ACCOUNT_MISMATCH = "COMPANY_BANK_ACCOUNT_MISMATCH"
COMPANY_BANK_NAME_MISMATCH = "COMPANY_BANK_NAME_MISMATCH"
COMPANY_IFSC_MISMATCH = "COMPANY_IFSC_MISMATCH"


@dataclass(frozen=True, slots=True)
class PendingIssue:
    issue_code: str
    check_name: str
    field_name: str
    issue_type: IssueType
    expected_value: str | None
    actual_value: str | None
    description: str


class BuyerCompanyValidationAgent:
    def __init__(
        self,
        company_repo: CompanyRepository,
        invoice_repo: InvoiceRepository,
        validation_issue_repo: ValidationIssueRepository,
    ) -> None:
        self._company_repo = company_repo
        self._invoice_repo = invoice_repo
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
            "Starting buyer company validation",
            extra={
                "invoice_id": str(invoice_id),
            },
        )

        company = await self._company_repo.get_active_company()

        if company is None:
            logger.warning(
                "No active company found in company_master; "
                "skipping buyer company validation",
                extra={
                    "invoice_id": str(invoice_id),
                },
            )
            return build_validation_state(
                invoice_id=invoice_id,
                po_id=state.get("po_id"),
                issue_codes=issue_codes,
            )

        extracted = await self._invoice_repo.get_buyer_company_details(
            invoice_id,
        )

        if extracted is None:
            raise InvoiceNotFoundError(
                invoice_id=invoice_id,
            )

        pending_issues: list[PendingIssue] = []

        pending_issues.extend(
            self._validate_mandatory_fields_missing(
                extracted=extracted,
            ),
        )

        if not self._all_mandatory_fields_missing(
            extracted=extracted,
        ):
            pending_issues.extend(
                await self._validate_present_field_mismatches(
                    extracted=extracted,
                    company=company,
                ),
            )

        issue_codes = await self._persist_issues(
            invoice_id=invoice_id,
            pending_issues=pending_issues,
            issue_codes=issue_codes,
        )

        logger.info(
            "Completed buyer company validation",
            extra={
                "invoice_id": str(invoice_id),
                "issue_count": len(pending_issues),
                "issue_codes": issue_codes,
            },
        )

        return build_validation_state(
            invoice_id=invoice_id,
            po_id=state.get("po_id"),
            issue_codes=issue_codes,
        )

    @staticmethod
    def _has_company_address(
        extracted: BuyerCompanyExtractedRecord,
    ) -> bool:
        return has_text(
            extracted.billing_address,
        )

    @staticmethod
    def _all_mandatory_fields_missing(
        extracted: BuyerCompanyExtractedRecord,
    ) -> bool:
        return (
            not has_text(
                extracted.company_name,
            )
            and not has_text(
                extracted.gstin,
            )
            and not BuyerCompanyValidationAgent._has_company_address(
                extracted,
            )
        )

    def _validate_mandatory_fields_missing(
        self,
        extracted: BuyerCompanyExtractedRecord,
    ) -> list[PendingIssue]:
        company_name_missing = not has_text(
            extracted.company_name,
        )
        company_gstin_missing = not has_text(
            extracted.gstin,
        )
        company_address_missing = not self._has_company_address(
            extracted,
        )

        if (
            company_name_missing
            and company_gstin_missing
            and company_address_missing
        ):
            return [
                PendingIssue(
                    issue_code=COMPANY_DETAILS_MISSING,
                    check_name="company_details_missing",
                    field_name="company_details",
                    issue_type=IssueType.MISSING,
                    expected_value=None,
                    actual_value=None,
                    description=(
                        "Buyer company name, GSTIN, and address could not "
                        "be extracted from the invoice."
                    ),
                ),
            ]

        pending_issues: list[PendingIssue] = []

        if company_name_missing:
            pending_issues.append(
                PendingIssue(
                    issue_code=MISSING_COMPANY_NAME,
                    check_name="company_name_missing",
                    field_name="company_name",
                    issue_type=IssueType.MISSING,
                    expected_value=None,
                    actual_value=None,
                    description=(
                        "Buyer company name could not be extracted "
                        "from the invoice."
                    ),
                ),
            )

        if company_gstin_missing:
            pending_issues.append(
                PendingIssue(
                    issue_code=MISSING_COMPANY_GSTIN,
                    check_name="company_gstin_missing",
                    field_name="company_gstin",
                    issue_type=IssueType.MISSING,
                    expected_value=None,
                    actual_value=None,
                    description=(
                        "Buyer company GSTIN could not be extracted "
                        "from the invoice."
                    ),
                ),
            )

        if company_address_missing:
            pending_issues.append(
                PendingIssue(
                    issue_code=MISSING_COMPANY_ADDRESS,
                    check_name="company_address_missing",
                    field_name="company_address",
                    issue_type=IssueType.MISSING,
                    expected_value=None,
                    actual_value=None,
                    description=(
                        "Buyer company address could not be extracted "
                        "from the invoice."
                    ),
                ),
            )

        return pending_issues

    async def _validate_present_field_mismatches(
        self,
        extracted: BuyerCompanyExtractedRecord,
        company: CompanyRecord,
    ) -> list[PendingIssue]:
        pending_issues: list[PendingIssue] = []

        if has_text(
            extracted.company_name,
        ):
            pending_issues.extend(
                self._validate_company_name(
                    extracted=extracted,
                    company=company,
                ),
            )

        if has_text(
            extracted.gstin,
        ):
            pending_issues.extend(
                self._validate_gstin(
                    extracted=extracted,
                    company=company,
                ),
            )

        if self._has_company_address(
            extracted,
        ):
            pending_issues.extend(
                await self._validate_company_address(
                    extracted=extracted,
                    company=company,
                ),
            )

        if has_text(
            extracted.pan_number,
        ):
            pending_issues.extend(
                self._validate_pan(
                    extracted=extracted,
                    company=company,
                ),
            )

        if has_text(
            extracted.shipping_address,
        ):
            pending_issues.extend(
                await self._validate_shipping_address(
                    extracted=extracted,
                    company=company,
                ),
            )

        if has_text(
            extracted.email,
        ):
            pending_issues.extend(
                self._validate_email(
                    extracted=extracted,
                    company=company,
                ),
            )

        if has_text(
            extracted.phone,
        ):
            pending_issues.extend(
                self._validate_phone(
                    extracted=extracted,
                    company=company,
                ),
            )

        pending_issues.extend(
            self._validate_bank_details(
                extracted=extracted,
            ),
        )

        return pending_issues

    def _validate_company_name(
        self,
        extracted: BuyerCompanyExtractedRecord,
        company: CompanyRecord,
    ) -> list[PendingIssue]:
        if not has_text(
            extracted.company_name,
        ):
            return []

        extracted_name = extracted.company_name
        assert extracted_name is not None

        if normalize_company_name_for_exact_match(
            extracted_name,
        ) == normalize_company_name_for_exact_match(
            company.company_name,
        ):
            return []

        try:
            match_result = compare_company_names_semantically(
                extracted=extracted_name,
                master=company.company_name,
            )
        except LLMServiceError:
            logger.exception(
                "LLM company name comparison failed",
            )
            return []

        if match_result.is_match:
            logger.info(
                "Company name matched semantically",
                extra={
                    "reason": match_result.reason,
                },
            )
            return []

        return [
            PendingIssue(
                issue_code=COMPANY_NAME_MISMATCH,
                check_name="company_name",
                field_name="company_name",
                issue_type=IssueType.MISMATCH,
                expected_value=company.company_name,
                actual_value=extracted_name,
                description=(
                    "Extracted buyer company name does not match "
                    "the active company master record."
                ),
            ),
        ]

    def _validate_gstin(
        self,
        extracted: BuyerCompanyExtractedRecord,
        company: CompanyRecord,
    ) -> list[PendingIssue]:
        if not has_text(
            extracted.gstin,
        ):
            return []

        extracted_gstin = extracted.gstin
        assert extracted_gstin is not None

        if normalize_gstin(
            extracted_gstin,
        ) == normalize_gstin(
            company.gstin,
        ):
            return []

        return [
            PendingIssue(
                issue_code=COMPANY_GSTIN_MISMATCH,
                check_name="company_gstin",
                field_name="company_gstin",
                issue_type=IssueType.MISMATCH,
                expected_value=company.gstin,
                actual_value=extracted_gstin,
                description=(
                    "Extracted buyer company GSTIN does not match "
                    "the active company master record."
                ),
            ),
        ]

    def _validate_pan(
        self,
        extracted: BuyerCompanyExtractedRecord,
        company: CompanyRecord,
    ) -> list[PendingIssue]:
        if not has_text(
            extracted.pan_number,
        ):
            return []

        if not has_text(
            company.pan_number,
        ):
            return []

        extracted_pan = extracted.pan_number
        master_pan = company.pan_number
        assert extracted_pan is not None
        assert master_pan is not None

        if normalize_pan(
            extracted_pan,
        ) == normalize_pan(
            master_pan,
        ):
            return []

        return [
            PendingIssue(
                issue_code=COMPANY_PAN_MISMATCH,
                check_name="pan_number",
                field_name="pan_number",
                issue_type=IssueType.MISMATCH,
                expected_value=master_pan,
                actual_value=extracted_pan,
                description=(
                    "Extracted buyer company PAN does not match "
                    "the active company master record."
                ),
            ),
        ]

    async def _validate_company_address(
        self,
        extracted: BuyerCompanyExtractedRecord,
        company: CompanyRecord,
    ) -> list[PendingIssue]:
        return await self._validate_address(
            extracted_value=extracted.billing_address,
            master_value=company.billing_address,
            issue_code=COMPANY_ADDRESS_MISMATCH,
            check_name="company_address",
            field_name="company_address",
            mismatch_description=(
                "Extracted buyer company address does not match "
                "the active company master record."
            ),
        )

    async def _validate_shipping_address(
        self,
        extracted: BuyerCompanyExtractedRecord,
        company: CompanyRecord,
    ) -> list[PendingIssue]:
        return await self._validate_address(
            extracted_value=extracted.shipping_address,
            master_value=company.shipping_address,
            issue_code=COMPANY_SHIPPING_ADDRESS_MISMATCH,
            check_name="shipping_address",
            field_name="shipping_address",
            mismatch_description=(
                "Extracted buyer company shipping address does not match "
                "the active company master record."
            ),
        )

    async def _validate_address(
        self,
        extracted_value: str | None,
        master_value: str | None,
        issue_code: str,
        check_name: str,
        field_name: str,
        mismatch_description: str,
    ) -> list[PendingIssue]:
        if not has_text(
            extracted_value,
        ):
            return []

        if not has_text(
            master_value,
        ):
            return []

        extracted_address = extracted_value
        master_address = master_value
        assert extracted_address is not None
        assert master_address is not None

        normalized_extracted = normalize_address(
            extracted_address,
        )
        normalized_master = normalize_address(
            master_address,
        )

        if normalized_extracted.casefold() == normalized_master.casefold():
            return []

        try:
            match_result = compare_addresses_semantically(
                extracted=normalized_extracted,
                master=normalized_master,
            )
        except LLMServiceError:
            logger.exception(
                "LLM address comparison failed",
                extra={
                    "field_name": field_name,
                },
            )
            return []

        if match_result.is_match:
            logger.info(
                "Address matched semantically",
                extra={
                    "field_name": field_name,
                    "reason": match_result.reason,
                },
            )
            return []

        return [
            PendingIssue(
                issue_code=issue_code,
                check_name=check_name,
                field_name=field_name,
                issue_type=IssueType.MISMATCH,
                expected_value=master_address,
                actual_value=extracted_address,
                description=mismatch_description,
            ),
        ]

    def _validate_email(
        self,
        extracted: BuyerCompanyExtractedRecord,
        company: CompanyRecord,
    ) -> list[PendingIssue]:
        if not has_text(
            extracted.email,
        ):
            return []

        if not has_text(
            company.email,
        ):
            return []

        extracted_email = extracted.email
        master_email = company.email
        assert extracted_email is not None
        assert master_email is not None

        if normalize_email(
            extracted_email,
        ) == normalize_email(
            master_email,
        ):
            return []

        return [
            PendingIssue(
                issue_code=COMPANY_EMAIL_MISMATCH,
                check_name="email",
                field_name="email",
                issue_type=IssueType.MISMATCH,
                expected_value=master_email,
                actual_value=extracted_email,
                description=(
                    "Extracted buyer company email does not match "
                    "the active company master record."
                ),
            ),
        ]

    def _validate_phone(
        self,
        extracted: BuyerCompanyExtractedRecord,
        company: CompanyRecord,
    ) -> list[PendingIssue]:
        if not has_text(
            extracted.phone,
        ):
            return []

        if not has_text(
            company.phone,
        ):
            return []

        extracted_phone = extracted.phone
        master_phone = company.phone
        assert extracted_phone is not None
        assert master_phone is not None

        if normalize_phone(
            extracted_phone,
        ) == normalize_phone(
            master_phone,
        ):
            return []

        return [
            PendingIssue(
                issue_code=COMPANY_PHONE_MISMATCH,
                check_name="phone",
                field_name="phone",
                issue_type=IssueType.MISMATCH,
                expected_value=master_phone,
                actual_value=extracted_phone,
                description=(
                    "Extracted buyer company phone number does not match "
                    "the active company master record."
                ),
            ),
        ]

    def _validate_bank_details(
        self,
        extracted: BuyerCompanyExtractedRecord,
    ) -> list[PendingIssue]:
        has_bank_data = any(
            has_text(value)
            for value in (
                extracted.bank_account_number,
                extracted.bank_name,
                extracted.ifsc_code,
            )
        )

        if has_bank_data:
            logger.info(
                "Skipping buyer bank detail validation; "
                "company master has no bank reference fields",
            )

        return []

    async def _persist_issues(
        self,
        invoice_id: UUID,
        pending_issues: list[PendingIssue],
        issue_codes: list[str],
    ) -> list[str]:
        updated_codes = list(
            issue_codes,
        )

        for pending_issue in pending_issues:
            await self._validation_issue_repo.create_issue(
                invoice_id=invoice_id,
                issue=ValidationIssueCreate(
                    check_stage=CHECK_STAGE,
                    check_name=pending_issue.check_name,
                    field_name=pending_issue.field_name,
                    issue_type=pending_issue.issue_type,
                    issue_code=pending_issue.issue_code,
                    expected_value=pending_issue.expected_value,
                    actual_value=pending_issue.actual_value,
                    description=pending_issue.description,
                    status=ValidationIssueStatus.OPEN,
                ),
            )

            if pending_issue.issue_code not in updated_codes:
                updated_codes.append(
                    pending_issue.issue_code,
                )

        return updated_codes
