from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.control.validation_flow import build_validation_state
from src.core.exceptions.llm_exc import LLMServiceError
from src.data.models.postgres.enums import (
    IssueType,
    ValidationIssueStatus,
    VendorStatus,
)
from src.data.repositories.shared.validation_issue_repository import (
    ValidationIssueCreate,
    ValidationIssueRepository,
)
from src.data.repositories.vendor_resolution.invoice_extracted_vendor_repository import (
    ExtractedVendorRecord,
    InvoiceExtractedVendorRepository,
)
from src.data.repositories.vendor_resolution.vendor_repository import (
    VendorRecord,
    VendorRepository,
)
from src.utils.company_matching_utils import (
    has_text,
    normalize_address,
    normalize_bank_account,
    normalize_bank_name,
    normalize_company_name_for_exact_match,
    normalize_gstin,
    normalize_ifsc,
    normalize_phone,
)
from src.utils.llm_client import (
    compare_addresses_semantically,
    compare_vendor_names_semantically,
)

logger = logging.getLogger(__name__)

CHECK_STAGE = "vendor_resolution"

VENDOR_DETAILS_MISSING = "VENDOR_DETAILS_MISSING"
MISSING_VENDOR_NAME = "MISSING_VENDOR_NAME"
MISSING_VENDOR_GSTIN = "MISSING_VENDOR_GSTIN"
MISSING_VENDOR_ADDRESS = "MISSING_VENDOR_ADDRESS"
DUPLICATE_VENDOR_GSTIN = "DUPLICATE_VENDOR_GSTIN"
AMBIGUOUS_VENDOR = "AMBIGUOUS_VENDOR"
VENDOR_NOT_FOUND = "VENDOR_NOT_FOUND"
VENDOR_NAME_MISMATCH = "VENDOR_NAME_MISMATCH"
VENDOR_GSTIN_MISMATCH = "VENDOR_GSTIN_MISMATCH"
VENDOR_PHONE_MISMATCH = "VENDOR_PHONE_MISMATCH"
VENDOR_ADDRESS_MISMATCH = "VENDOR_ADDRESS_MISMATCH"
VENDOR_BANK_ACCOUNT_MISMATCH = "VENDOR_BANK_ACCOUNT_MISMATCH"
VENDOR_IFSC_MISMATCH = "VENDOR_IFSC_MISMATCH"
VENDOR_BANK_NAME_MISMATCH = "VENDOR_BANK_NAME_MISMATCH"
VENDOR_BLACKLISTED = "VENDOR_BLACKLISTED"
VENDOR_SUSPENDED = "VENDOR_SUSPENDED"

VENDOR_NOT_FOUND_DESCRIPTION = (
    "Unable to resolve a vendor from the extracted invoice details."
)


@dataclass(frozen=True, slots=True)
class PendingIssue:
    issue_code: str
    check_name: str
    field_name: str
    issue_type: IssueType
    expected_value: str | None
    actual_value: str | None
    description: str


class VendorResolutionAgent:
    def __init__(
        self,
        extracted_vendor_repo: InvoiceExtractedVendorRepository,
        vendor_repo: VendorRepository,
        validation_issue_repo: ValidationIssueRepository,
    ) -> None:
        self._extracted_vendor_repo = extracted_vendor_repo
        self._vendor_repo = vendor_repo
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
            "Starting vendor resolution",
            extra={
                "invoice_id": str(invoice_id),
            },
        )

        extracted = await self._extracted_vendor_repo.get_by_invoice_id(
            invoice_id,
        )

        if extracted is None:
            issue_codes = await self._finish_with_issues(
                invoice_id=invoice_id,
                pending_issues=[
                    PendingIssue(
                        issue_code=VENDOR_DETAILS_MISSING,
                        check_name="vendor_details_missing",
                        field_name="vendor_details",
                        issue_type=IssueType.MISSING,
                        expected_value=None,
                        actual_value=None,
                        description=(
                            "Vendor name, GSTIN, and address could not "
                            "be extracted from the invoice."
                        ),
                    ),
                ],
                issue_codes=issue_codes,
            )
            return build_validation_state(
                invoice_id=invoice_id,
                po_id=state.get("po_id"),
                issue_codes=issue_codes,
            )

        missing_issues = self._validate_mandatory_fields_missing(
            extracted=extracted,
        )

        if self._all_mandatory_fields_missing(
            extracted=extracted,
        ):
            issue_codes = await self._finish_with_issues(
                invoice_id=invoice_id,
                pending_issues=missing_issues,
                issue_codes=issue_codes,
            )
            return build_validation_state(
                invoice_id=invoice_id,
                po_id=state.get("po_id"),
                issue_codes=issue_codes,
            )

        issue_codes = await self._finish_with_issues(
            invoice_id=invoice_id,
            pending_issues=missing_issues,
            issue_codes=issue_codes,
        )

        resolved_vendor, pending_issues, stop = (
            await self._resolve_vendor(
                invoice_id=invoice_id,
                extracted=extracted,
            )
        )

        if stop:
            issue_codes = await self._finish_with_issues(
                invoice_id=invoice_id,
                pending_issues=pending_issues,
                issue_codes=issue_codes,
            )
            return build_validation_state(
                invoice_id=invoice_id,
                po_id=state.get("po_id"),
                issue_codes=issue_codes,
            )

        if resolved_vendor is None:
            pending_issues.append(
                PendingIssue(
                    issue_code=VENDOR_NOT_FOUND,
                    check_name="vendor_resolution",
                    field_name="vendor_name",
                    issue_type=IssueType.MISSING,
                    expected_value=None,
                    actual_value=extracted.vendor_name,
                    description=VENDOR_NOT_FOUND_DESCRIPTION,
                ),
            )
            issue_codes = await self._finish_with_issues(
                invoice_id=invoice_id,
                pending_issues=pending_issues,
                issue_codes=issue_codes,
            )
            return build_validation_state(
                invoice_id=invoice_id,
                po_id=state.get("po_id"),
                issue_codes=issue_codes,
            )

        await self._extracted_vendor_repo.update_vendor_master_id(
            invoice_id,
            resolved_vendor.id,
        )

        await self._validation_issue_repo.mark_issue_resolved(
            invoice_id,
            VENDOR_NOT_FOUND,
        )

        logger.info(
            "Vendor resolved",
            extra={
                "invoice_id": str(invoice_id),
                "vendor_master_id": str(resolved_vendor.id),
                "vendor_name": resolved_vendor.vendor_name,
            },
        )

        pending_issues.extend(
            await self._run_verification_checks(
                extracted=extracted,
                vendor=resolved_vendor,
            ),
        )
        pending_issues.extend(
            self._validate_vendor_status(
                vendor=resolved_vendor,
            ),
        )

        issue_codes = await self._finish_with_issues(
            invoice_id=invoice_id,
            pending_issues=pending_issues,
            issue_codes=issue_codes,
        )
        issue_codes = [
            code
            for code in issue_codes
            if code != VENDOR_NOT_FOUND
        ]

        logger.info(
            "Completed vendor resolution",
            extra={
                "invoice_id": str(invoice_id),
                "vendor_master_id": str(resolved_vendor.id),
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
    def _has_vendor_address(
        extracted: ExtractedVendorRecord,
    ) -> bool:
        return has_text(
            extracted.address,
        )

    @staticmethod
    def _all_mandatory_fields_missing(
        extracted: ExtractedVendorRecord,
    ) -> bool:
        return (
            not has_text(
                extracted.vendor_name,
            )
            and not has_text(
                extracted.vendor_gstin,
            )
            and not VendorResolutionAgent._has_vendor_address(
                extracted,
            )
        )

    def _validate_mandatory_fields_missing(
        self,
        extracted: ExtractedVendorRecord,
    ) -> list[PendingIssue]:
        vendor_name_missing = not has_text(
            extracted.vendor_name,
        )
        vendor_gstin_missing = not has_text(
            extracted.vendor_gstin,
        )
        vendor_address_missing = not self._has_vendor_address(
            extracted,
        )

        if (
            vendor_name_missing
            and vendor_gstin_missing
            and vendor_address_missing
        ):
            return [
                PendingIssue(
                    issue_code=VENDOR_DETAILS_MISSING,
                    check_name="vendor_details_missing",
                    field_name="vendor_details",
                    issue_type=IssueType.MISSING,
                    expected_value=None,
                    actual_value=None,
                    description=(
                        "Vendor name, GSTIN, and address could not be "
                        "extracted from the invoice."
                    ),
                ),
            ]

        pending_issues: list[PendingIssue] = []

        if vendor_name_missing:
            pending_issues.append(
                PendingIssue(
                    issue_code=MISSING_VENDOR_NAME,
                    check_name="vendor_name_missing",
                    field_name="vendor_name",
                    issue_type=IssueType.MISSING,
                    expected_value=None,
                    actual_value=None,
                    description=(
                        "Vendor name could not be extracted from the "
                        "invoice."
                    ),
                ),
            )

        if vendor_gstin_missing:
            pending_issues.append(
                PendingIssue(
                    issue_code=MISSING_VENDOR_GSTIN,
                    check_name="vendor_gstin_missing",
                    field_name="vendor_gstin",
                    issue_type=IssueType.MISSING,
                    expected_value=None,
                    actual_value=None,
                    description=(
                        "Vendor GSTIN could not be extracted from the "
                        "invoice."
                    ),
                ),
            )

        if vendor_address_missing:
            pending_issues.append(
                PendingIssue(
                    issue_code=MISSING_VENDOR_ADDRESS,
                    check_name="vendor_address_missing",
                    field_name="vendor_address",
                    issue_type=IssueType.MISSING,
                    expected_value=None,
                    actual_value=None,
                    description=(
                        "Vendor address could not be extracted from the "
                        "invoice."
                    ),
                ),
            )

        return pending_issues

    async def _resolve_vendor(
        self,
        invoice_id: UUID,
        extracted: ExtractedVendorRecord,
    ) -> tuple[
        VendorRecord | None,
        list[PendingIssue],
        bool,
    ]:
        pending_issues: list[PendingIssue] = []

        gstin_result = await self._match_by_gstin(
            extracted=extracted,
        )
        if gstin_result.stop:
            return (
                None,
                list(gstin_result.pending_issues),
                True,
            )
        if gstin_result.vendor is not None:
            return (
                gstin_result.vendor,
                pending_issues,
                False,
            )

        bank_result = await self._match_by_bank(
            extracted=extracted,
        )
        if bank_result.stop:
            return (
                None,
                list(bank_result.pending_issues),
                True,
            )
        if bank_result.vendor is not None:
            return (
                bank_result.vendor,
                pending_issues,
                False,
            )

        name_result = await self._match_by_exact_name(
            extracted=extracted,
        )
        if name_result.stop:
            return (
                None,
                list(name_result.pending_issues),
                True,
            )
        if name_result.vendor is not None:
            return (
                name_result.vendor,
                pending_issues,
                False,
            )

        await self._ensure_vendor_not_found_issue(
            invoice_id=invoice_id,
            extracted=extracted,
        )

        llm_result = await self._match_by_llm_name(
            extracted=extracted,
        )
        if llm_result.stop:
            return (
                None,
                list(llm_result.pending_issues),
                True,
            )

        return (
            llm_result.vendor,
            list(llm_result.pending_issues),
            False,
        )

    async def _ensure_vendor_not_found_issue(
        self,
        invoice_id: UUID,
        extracted: ExtractedVendorRecord,
    ) -> None:
        await self._validation_issue_repo.create_issue(
            invoice_id=invoice_id,
            issue=ValidationIssueCreate(
                check_stage=CHECK_STAGE,
                check_name="vendor_resolution",
                field_name="vendor_name",
                issue_type=IssueType.MISSING,
                issue_code=VENDOR_NOT_FOUND,
                expected_value=None,
                actual_value=extracted.vendor_name,
                description=VENDOR_NOT_FOUND_DESCRIPTION,
                status=ValidationIssueStatus.OPEN,
            ),
        )

    async def _match_by_gstin(
        self,
        extracted: ExtractedVendorRecord,
    ) -> _MatchResult:
        if not has_text(
            extracted.vendor_gstin,
        ):
            return _MatchResult()

        extracted_gstin = extracted.vendor_gstin
        assert extracted_gstin is not None

        matches = await self._vendor_repo.find_by_gstin(
            extracted_gstin,
        )

        if len(matches) > 1:
            return _MatchResult(
                stop=True,
                pending_issues=(
                    PendingIssue(
                        issue_code=DUPLICATE_VENDOR_GSTIN,
                        check_name="gstin_match",
                        field_name="vendor_gstin",
                        issue_type=IssueType.DUPLICATE,
                        expected_value=None,
                        actual_value=extracted_gstin,
                        description=(
                            "Multiple vendors found with the same GSTIN."
                        ),
                    ),
                ),
            )

        if len(matches) == 1:
            return _MatchResult(
                vendor=matches[0],
            )

        return _MatchResult()

    async def _match_by_bank(
        self,
        extracted: ExtractedVendorRecord,
    ) -> _MatchResult:
        if not has_text(
            extracted.bank_account_number,
        ) or not has_text(
            extracted.ifsc_code,
        ):
            return _MatchResult()

        bank_account = extracted.bank_account_number
        ifsc_code = extracted.ifsc_code
        assert bank_account is not None
        assert ifsc_code is not None

        matches = await self._vendor_repo.find_by_bank_account_and_ifsc(
            bank_account,
            ifsc_code,
        )

        if len(matches) > 1:
            return _MatchResult(
                stop=True,
                pending_issues=(
                    PendingIssue(
                        issue_code=AMBIGUOUS_VENDOR,
                        check_name="bank_match",
                        field_name="bank_account_number",
                        issue_type=IssueType.AMBIGUOUS,
                        expected_value=None,
                        actual_value=bank_account,
                        description=(
                            "Multiple vendors matched extracted bank "
                            "account and IFSC."
                        ),
                    ),
                ),
            )

        if len(matches) == 1:
            return _MatchResult(
                vendor=matches[0],
            )

        return _MatchResult()

    async def _match_by_exact_name(
        self,
        extracted: ExtractedVendorRecord,
    ) -> _MatchResult:
        if not has_text(
            extracted.vendor_name,
        ):
            return _MatchResult()

        vendor_name = extracted.vendor_name
        assert vendor_name is not None

        matches = await self._vendor_repo.find_by_exact_vendor_name(
            vendor_name,
        )

        if len(matches) > 1:
            return _MatchResult(
                stop=True,
                pending_issues=(
                    PendingIssue(
                        issue_code=AMBIGUOUS_VENDOR,
                        check_name="exact_name_match",
                        field_name="vendor_name",
                        issue_type=IssueType.AMBIGUOUS,
                        expected_value=None,
                        actual_value=vendor_name,
                        description=(
                            "Multiple vendors matched extracted vendor "
                            "name exactly."
                        ),
                    ),
                ),
            )

        if len(matches) == 1:
            return _MatchResult(
                vendor=matches[0],
            )

        return _MatchResult()

    async def _match_by_llm_name(
        self,
        extracted: ExtractedVendorRecord,
    ) -> _MatchResult:
        if not has_text(
            extracted.vendor_name,
        ):
            return _MatchResult()

        vendor_name = extracted.vendor_name
        assert vendor_name is not None

        active_vendors = await self._vendor_repo.get_active_vendors()
        llm_matches: list[VendorRecord] = []

        for vendor in active_vendors:
            try:
                match_result = compare_vendor_names_semantically(
                    extracted=vendor_name,
                    master=vendor.vendor_name,
                )
            except LLMServiceError:
                logger.exception(
                    "LLM vendor name comparison failed",
                    extra={
                        "vendor_master_id": str(vendor.id),
                    },
                )
                continue

            if match_result.is_match:
                llm_matches.append(
                    vendor,
                )

        if not llm_matches:
            return _MatchResult(
                stop=True,
                pending_issues=(
                    PendingIssue(
                        issue_code=VENDOR_NOT_FOUND,
                        check_name="llm_name_match",
                        field_name="vendor_name",
                        issue_type=IssueType.MISSING,
                        expected_value=None,
                        actual_value=vendor_name,
                        description=VENDOR_NOT_FOUND_DESCRIPTION,
                    ),
                ),
            )

        if len(llm_matches) > 1:
            return _MatchResult(
                stop=True,
                pending_issues=(
                    PendingIssue(
                        issue_code=AMBIGUOUS_VENDOR,
                        check_name="llm_name_match",
                        field_name="vendor_name",
                        issue_type=IssueType.AMBIGUOUS,
                        expected_value=None,
                        actual_value=vendor_name,
                        description=(
                            "Multiple active vendors matched extracted "
                            "vendor name using LLM resolution."
                        ),
                    ),
                ),
            )

        return _MatchResult(
            vendor=llm_matches[0],
        )

    async def _run_verification_checks(
        self,
        extracted: ExtractedVendorRecord,
        vendor: VendorRecord,
    ) -> list[PendingIssue]:
        issues: list[PendingIssue] = []

        issues.extend(
            self._verify_vendor_name(
                extracted=extracted,
                vendor=vendor,
            ),
        )
        issues.extend(
            self._verify_gstin(
                extracted=extracted,
                vendor=vendor,
            ),
        )
        issues.extend(
            self._verify_phone(
                extracted=extracted,
                vendor=vendor,
            ),
        )
        issues.extend(
            await self._verify_address(
                extracted=extracted,
                vendor=vendor,
            ),
        )
        issues.extend(
            self._verify_bank_account(
                extracted=extracted,
                vendor=vendor,
            ),
        )
        issues.extend(
            self._verify_ifsc(
                extracted=extracted,
                vendor=vendor,
            ),
        )
        issues.extend(
            self._verify_bank_name(
                extracted=extracted,
                vendor=vendor,
            ),
        )

        return issues

    def _verify_vendor_name(
        self,
        extracted: ExtractedVendorRecord,
        vendor: VendorRecord,
    ) -> list[PendingIssue]:
        if not has_text(
            extracted.vendor_name,
        ):
            return []

        extracted_name = extracted.vendor_name
        assert extracted_name is not None

        if normalize_company_name_for_exact_match(
            extracted_name,
        ) == normalize_company_name_for_exact_match(
            vendor.vendor_name,
        ):
            return []

        try:
            match_result = compare_vendor_names_semantically(
                extracted=extracted_name,
                master=vendor.vendor_name,
            )
        except LLMServiceError:
            logger.exception(
                "LLM vendor name verification failed",
            )
            return []

        if match_result.is_match:
            return []

        return [
            PendingIssue(
                issue_code=VENDOR_NAME_MISMATCH,
                check_name="vendor_name_verification",
                field_name="vendor_name",
                issue_type=IssueType.MISMATCH,
                expected_value=vendor.vendor_name,
                actual_value=extracted_name,
                description=(
                    "Extracted vendor name does not match the resolved "
                    "vendor master record."
                ),
            ),
        ]

    def _verify_gstin(
        self,
        extracted: ExtractedVendorRecord,
        vendor: VendorRecord,
    ) -> list[PendingIssue]:
        if not has_text(
            extracted.vendor_gstin,
        ):
            return []

        extracted_gstin = extracted.vendor_gstin
        assert extracted_gstin is not None

        if vendor.gstin is None:
            return []

        if normalize_gstin(
            extracted_gstin,
        ) == normalize_gstin(
            vendor.gstin,
        ):
            return []

        return [
            PendingIssue(
                issue_code=VENDOR_GSTIN_MISMATCH,
                check_name="gstin_verification",
                field_name="vendor_gstin",
                issue_type=IssueType.MISMATCH,
                expected_value=vendor.gstin,
                actual_value=extracted_gstin,
                description=(
                    "Extracted vendor GSTIN does not match the resolved "
                    "vendor master record."
                ),
            ),
        ]

    def _verify_phone(
        self,
        extracted: ExtractedVendorRecord,
        vendor: VendorRecord,
    ) -> list[PendingIssue]:
        if not has_text(
            extracted.vendor_phone,
        ):
            return []

        extracted_phone = extracted.vendor_phone
        assert extracted_phone is not None

        if not has_text(
            vendor.phone,
        ):
            return []

        vendor_phone = vendor.phone
        assert vendor_phone is not None

        if normalize_phone(
            extracted_phone,
        ) == normalize_phone(
            vendor_phone,
        ):
            return []

        return [
            PendingIssue(
                issue_code=VENDOR_PHONE_MISMATCH,
                check_name="phone_verification",
                field_name="vendor_phone",
                issue_type=IssueType.MISMATCH,
                expected_value=vendor_phone,
                actual_value=extracted_phone,
                description=(
                    "Extracted vendor phone number does not match the "
                    "resolved vendor master record."
                ),
            ),
        ]

    async def _verify_address(
        self,
        extracted: ExtractedVendorRecord,
        vendor: VendorRecord,
    ) -> list[PendingIssue]:
        if not has_text(
            extracted.address,
        ):
            return []

        extracted_address = extracted.address
        assert extracted_address is not None

        if not has_text(
            vendor.address,
        ):
            return []

        vendor_address = vendor.address
        assert vendor_address is not None

        normalized_extracted = normalize_address(
            extracted_address,
        )
        normalized_vendor = normalize_address(
            vendor_address,
        )

        if normalized_extracted.casefold() == normalized_vendor.casefold():
            return []

        try:
            match_result = compare_addresses_semantically(
                extracted=normalized_extracted,
                master=normalized_vendor,
            )
        except LLMServiceError:
            logger.exception(
                "LLM vendor address comparison failed",
            )
            return []

        if match_result.is_match:
            return []

        return [
            PendingIssue(
                issue_code=VENDOR_ADDRESS_MISMATCH,
                check_name="address_verification",
                field_name="vendor_address",
                issue_type=IssueType.MISMATCH,
                expected_value=vendor_address,
                actual_value=extracted_address,
                description=(
                    "Extracted vendor address does not match the resolved "
                    "vendor master record."
                ),
            ),
        ]

    def _verify_bank_account(
        self,
        extracted: ExtractedVendorRecord,
        vendor: VendorRecord,
    ) -> list[PendingIssue]:
        if not has_text(
            extracted.bank_account_number,
        ):
            return []

        extracted_account = extracted.bank_account_number
        assert extracted_account is not None

        if not has_text(
            vendor.bank_account_number,
        ):
            return []

        vendor_account = vendor.bank_account_number
        assert vendor_account is not None

        if normalize_bank_account(
            extracted_account,
        ) == normalize_bank_account(
            vendor_account,
        ):
            return []

        return [
            PendingIssue(
                issue_code=VENDOR_BANK_ACCOUNT_MISMATCH,
                check_name="bank_account_verification",
                field_name="bank_account_number",
                issue_type=IssueType.MISMATCH,
                expected_value=vendor_account,
                actual_value=extracted_account,
                description=(
                    "Extracted vendor bank account number does not match "
                    "the resolved vendor master record."
                ),
            ),
        ]

    def _verify_ifsc(
        self,
        extracted: ExtractedVendorRecord,
        vendor: VendorRecord,
    ) -> list[PendingIssue]:
        if not has_text(
            extracted.ifsc_code,
        ):
            return []

        extracted_ifsc = extracted.ifsc_code
        assert extracted_ifsc is not None

        if not has_text(
            vendor.ifsc_code,
        ):
            return []

        vendor_ifsc = vendor.ifsc_code
        assert vendor_ifsc is not None

        if normalize_ifsc(
            extracted_ifsc,
        ) == normalize_ifsc(
            vendor_ifsc,
        ):
            return []

        return [
            PendingIssue(
                issue_code=VENDOR_IFSC_MISMATCH,
                check_name="ifsc_verification",
                field_name="ifsc_code",
                issue_type=IssueType.MISMATCH,
                expected_value=vendor_ifsc,
                actual_value=extracted_ifsc,
                description=(
                    "Extracted vendor IFSC code does not match the "
                    "resolved vendor master record."
                ),
            ),
        ]

    def _verify_bank_name(
        self,
        extracted: ExtractedVendorRecord,
        vendor: VendorRecord,
    ) -> list[PendingIssue]:
        if not has_text(
            extracted.bank_name,
        ):
            return []

        extracted_bank_name = extracted.bank_name
        assert extracted_bank_name is not None

        if not has_text(
            vendor.bank_name,
        ):
            return []

        vendor_bank_name = vendor.bank_name
        assert vendor_bank_name is not None

        if normalize_bank_name(
            extracted_bank_name,
        ) == normalize_bank_name(
            vendor_bank_name,
        ):
            return []

        return [
            PendingIssue(
                issue_code=VENDOR_BANK_NAME_MISMATCH,
                check_name="bank_name_verification",
                field_name="bank_name",
                issue_type=IssueType.MISMATCH,
                expected_value=vendor_bank_name,
                actual_value=extracted_bank_name,
                description=(
                    "Extracted vendor bank name does not match the "
                    "resolved vendor master record."
                ),
            ),
        ]

    def _validate_vendor_status(
        self,
        vendor: VendorRecord,
    ) -> list[PendingIssue]:
        if vendor.status == VendorStatus.BLACKLISTED:
            return [
                PendingIssue(
                    issue_code=VENDOR_BLACKLISTED,
                    check_name="vendor_status",
                    field_name="status",
                    issue_type=IssueType.INVALID,
                    expected_value=VendorStatus.ACTIVE.value,
                    actual_value=VendorStatus.BLACKLISTED.value,
                    description=(
                        "Resolved vendor is blacklisted in vendor master."
                    ),
                ),
            ]

        if vendor.status == VendorStatus.SUSPENDED:
            return [
                PendingIssue(
                    issue_code=VENDOR_SUSPENDED,
                    check_name="vendor_status",
                    field_name="status",
                    issue_type=IssueType.INVALID,
                    expected_value=VendorStatus.ACTIVE.value,
                    actual_value=VendorStatus.SUSPENDED.value,
                    description=(
                        "Resolved vendor is suspended in vendor master."
                    ),
                ),
            ]

        return []

    async def _finish_with_issues(
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


@dataclass(frozen=True, slots=True)
class _MatchResult:
    vendor: VendorRecord | None = None
    pending_issues: tuple[PendingIssue, ...] = ()
    stop: bool = False
