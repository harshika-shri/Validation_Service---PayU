from __future__ import annotations

RECOVERY_MESSAGES: dict[str, str] = {
    "MISSING_INVOICE_NUMBER": (
        "Missing invoice number was recovered from the associated email."
    ),
    "VENDOR_NOT_FOUND": (
        "Vendor was successfully identified after initial lookup "
        "did not find a direct match."
    ),
    "PO_MISSING": (
        "No PO number could be extracted from the invoice."
    ),
    "PO_RECOVERED": (
        "A replacement PO candidate was identified using vendor, date, "
        "and invoice content after the extracted PO reference could not "
        "be used."
    ),
    "PO_RESOLUTION_BLOCKED": (
        "PO resolution could not proceed because vendor resolution failed."
    ),
    "PO_NOT_FOUND": (
        "No PO number could be extracted from the invoice."
    ),
    "INVALID_PO_REFERENCE": (
        "The purchase order number on the invoice did not match "
        "the line items billed. The system identified the correct "
        "purchase order(s) from available orders."
    ),
}

WAIVED_MESSAGES: dict[str, str] = {
    "MISSING_INVOICE_NUMBER": (
        "Original invoice number could not be recovered. "
        "A system-generated invoice identifier was assigned to allow processing."
    ),
}

OPEN_ISSUE_MESSAGES: dict[str, str] = {
    "MISSING_INVOICE_NUMBER": (
        "Invoice number is missing on the submitted invoice."
    ),
    "VENDOR_NOT_FOUND": (
        "Unable to resolve a vendor from the extracted invoice details."
    ),
    "VENDOR_DETAILS_MISSING": (
        "Vendor name, GSTIN, and address could not be extracted from "
        "the invoice."
    ),
    "MISSING_VENDOR_NAME": (
        "Vendor name could not be extracted from the invoice."
    ),
    "MISSING_VENDOR_GSTIN": (
        "Vendor GSTIN could not be extracted from the invoice."
    ),
    "MISSING_VENDOR_ADDRESS": (
        "Vendor address could not be extracted from the invoice."
    ),
    "VENDOR_NAME_MISMATCH": (
        "Extracted vendor name does not match the resolved vendor master "
        "record."
    ),
    "PO_NOT_FOUND": (
        "Referenced purchase order number was not found."
    ),
    "PO_MISSING": (
        "No PO number could be extracted from the invoice."
    ),
    "PO_RECOVERED": (
        "A replacement PO candidate was identified after the extracted "
        "PO reference could not be used."
    ),
    "PO_RESOLUTION_BLOCKED": (
        "PO resolution could not proceed because vendor resolution failed."
    ),
    "INVALID_PO_REFERENCE": (
        "Extracted PO number does not exist in the system."
    ),
    "COMPANY_DETAILS_MISSING": (
        "Buyer company name, GSTIN, and address could not be extracted "
        "from the invoice."
    ),
    "MISSING_COMPANY_NAME": (
        "Buyer company name could not be extracted from the invoice."
    ),
    "MISSING_COMPANY_GSTIN": (
        "Buyer company GSTIN could not be extracted from the invoice."
    ),
    "MISSING_COMPANY_ADDRESS": (
        "Buyer company address could not be extracted from the invoice."
    ),
    "COMPANY_NAME_MISMATCH": (
        "Extracted buyer company name does not match the active company "
        "master record."
    ),
    "COMPANY_GSTIN_MISMATCH": (
        "Extracted buyer company GSTIN does not match the active company "
        "master record."
    ),
    "COMPANY_PAN_MISMATCH": (
        "Extracted buyer company PAN does not match the active company "
        "master record."
    ),
    "COMPANY_ADDRESS_MISMATCH": (
        "Extracted buyer company address does not match the active company "
        "master record."
    ),
    "COMPANY_SHIPPING_ADDRESS_MISMATCH": (
        "Extracted buyer company shipping address does not match the active "
        "company master record."
    ),
    "COMPANY_EMAIL_MISMATCH": (
        "Extracted buyer company email does not match the active company "
        "master record."
    ),
    "COMPANY_PHONE_MISMATCH": (
        "Extracted buyer company phone number does not match the active "
        "company master record."
    ),
    "COMPANY_BANK_ACCOUNT_MISMATCH": (
        "Buyer bank account differs from the company master record."
    ),
    "COMPANY_BANK_NAME_MISMATCH": (
        "Buyer bank name differs from the company master record."
    ),
    "COMPANY_IFSC_MISMATCH": (
        "Buyer IFSC code differs from the company master record."
    ),
    "DUPLICATE_VENDOR_GSTIN": (
        "Multiple vendor master records share the same GSTIN."
    ),
    "AMBIGUOUS_VENDOR": (
        "Multiple vendor master records match the extracted vendor details."
    ),
    "VENDOR_GSTIN_MISMATCH": (
        "Extracted vendor GSTIN does not match the resolved vendor master "
        "record."
    ),
    "VENDOR_PHONE_MISMATCH": (
        "Extracted vendor phone number does not match the resolved vendor "
        "master record."
    ),
    "VENDOR_ADDRESS_MISMATCH": (
        "Extracted vendor address does not match the resolved vendor master "
        "record."
    ),
    "VENDOR_BANK_ACCOUNT_MISMATCH": (
        "Extracted vendor bank account number does not match the resolved "
        "vendor master record."
    ),
    "VENDOR_IFSC_MISMATCH": (
        "Extracted vendor IFSC code does not match the resolved vendor "
        "master record."
    ),
    "VENDOR_BANK_NAME_MISMATCH": (
        "Extracted vendor bank name does not match the resolved vendor "
        "master record."
    ),
    "VENDOR_BLACKLISTED": (
        "Vendor is blacklisted in the vendor master."
    ),
    "VENDOR_SUSPENDED": (
        "Vendor is suspended in the vendor master."
    ),
    "PO_CLOSED": (
        "Referenced purchase order is closed."
    ),
    "PO_UNRESOLVED": (
        "No suitable PO candidate could be identified."
    ),
    "PO_AMBIGUOUS": (
        "Multiple PO candidates satisfy the invoice and the system "
        "cannot confidently determine the correct one."
    ),
    "PO_VENDOR_CONFLICT": (
        "Resolved PO belongs to a vendor that conflicts with the vendor "
        "extracted from the invoice."
    ),
    "MISSING_PO_COVERAGE": (
        "One or more invoice lines lack purchase order coverage."
    ),
    "DUPLICATE_INVOICE_LINE": (
        "Duplicate invoice line items were detected."
    ),
    "UNMATCHED_LINE_ITEM": (
        "One or more invoice lines could not be matched to purchase orders."
    ),
    "AMBIGUOUS_LINE_MATCH": (
        "Multiple valid line allocation plans were found."
    ),
    "LINE_ITEM_VENDOR_CONFLICT": (
        "A matched purchase order line belongs to a different vendor."
    ),
    "QUANTITY_EXCEEDS_ORDERED": (
        "Billed quantity exceeds the purchase order ordered quantity."
    ),
    "QUANTITY_EXCEEDS_REMAINING": (
        "Billed quantity exceeds the remaining purchase order quantity."
    ),
    "INVALID_ALLOCATION": (
        "Line allocation totals do not match billed quantities."
    ),
    "UNIT_PRICE_VARIANCE": (
        "Unit price varies from the purchase order within tolerance."
    ),
    "UNIT_PRICE_MISMATCH": (
        "Unit price differs from the associated purchase order."
    ),
    "LINE_TOTAL_MISMATCH": (
        "Line total does not match quantity multiplied by unit price."
    ),
    "ALLOCATION_AMOUNT_MISMATCH": (
        "Allocated amount differs from the expected purchase order amount."
    ),
    "LINE_TAX_MISMATCH": (
        "Line tax amount differs from the expected value."
    ),
    "INVOICE_TAX_MISMATCH": (
        "Invoice tax amount differs from the expected value."
    ),
    "SUBTOTAL_MISMATCH": (
        "Invoice subtotal differs from the sum of line totals."
    ),
    "TOTAL_AMOUNT_MISMATCH": (
        "Invoice total amount differs from the associated purchase order amount."
    ),
    "ADDITIONAL_DISCOUNT_APPLIED": (
        "An additional discount was applied on the invoice."
    ),
    "DISCOUNT_AMOUNT_MISMATCH": (
        "Discount amount differs from the expected value."
    ),
    "ADDITIONAL_HANDLING_FEE": (
        "An additional handling fee appears on the invoice."
    ),
    "HANDLING_FEE_MISMATCH": (
        "Handling fee differs from the expected value."
    ),
    "ADDITIONAL_FREIGHT_CHARGE": (
        "An additional freight charge appears on the invoice."
    ),
    "FREIGHT_CHARGE_MISMATCH": (
        "Freight charge differs from the expected value."
    ),
    "ADDITIONAL_SHIPPING_CHARGE": (
        "An additional shipping charge appears on the invoice."
    ),
    "SHIPPING_CHARGE_MISMATCH": (
        "Shipping charge differs from the expected value."
    ),
    "ADDITIONAL_PROCESSING_FEE": (
        "An additional processing fee appears on the invoice."
    ),
    "PROCESSING_FEE_MISMATCH": (
        "Processing fee differs from the expected value."
    ),
    "ADDITIONAL_MISC_CHARGE": (
        "An additional miscellaneous charge appears on the invoice."
    ),
    "MISC_CHARGE_MISMATCH": (
        "Miscellaneous charge differs from the expected value."
    ),
    "ROUNDING_MISMATCH": (
        "Invoice rounding differs from the expected total."
    ),
    "DUPLICATE_INVOICE_NUMBER": (
        "This invoice number has already been used for this vendor."
    ),
    "POTENTIAL_DUPLICATE_INVOICE": (
        "This invoice closely resembles another invoice from the same vendor."
    ),
}

VENDOR_CLARIFICATION_TOPICS: dict[str, str] = {
    "PO_NOT_FOUND": "Verify correct purchase order reference.",
    "INVALID_PO_REFERENCE": "Verify correct purchase order reference.",
    "VENDOR_NOT_FOUND": "Confirm vendor identity details.",
    "VENDOR_DETAILS_MISSING": "Confirm vendor identity details.",
    "MISSING_VENDOR_NAME": "Confirm vendor name.",
    "MISSING_VENDOR_GSTIN": "Confirm vendor GSTIN.",
    "MISSING_VENDOR_ADDRESS": "Confirm vendor address.",
    "VENDOR_NAME_MISMATCH": "Confirm vendor name details.",
    "COMPANY_NAME_MISMATCH": "Confirm buyer company details.",
    "COMPANY_GSTIN_MISMATCH": "Confirm GSTIN details.",
    "COMPANY_PAN_MISMATCH": "Confirm PAN details.",
    "COMPANY_DETAILS_MISSING": "Confirm buyer company details.",
    "MISSING_COMPANY_NAME": "Confirm buyer company name.",
    "MISSING_COMPANY_GSTIN": "Confirm buyer company GSTIN.",
    "MISSING_COMPANY_ADDRESS": "Confirm buyer company address.",
    "COMPANY_ADDRESS_MISMATCH": "Confirm buyer address details.",
    "COMPANY_SHIPPING_ADDRESS_MISMATCH": "Confirm shipping address details.",
    "COMPANY_EMAIL_MISMATCH": "Confirm buyer contact email.",
    "COMPANY_PHONE_MISMATCH": "Confirm buyer contact phone number.",
    "COMPANY_BANK_ACCOUNT_MISMATCH": "Confirm buyer bank account details.",
    "COMPANY_BANK_NAME_MISMATCH": "Confirm buyer bank name.",
    "COMPANY_IFSC_MISMATCH": "Confirm buyer IFSC details.",
    "VENDOR_GSTIN_MISMATCH": "Confirm GSTIN details.",
    "VENDOR_PHONE_MISMATCH": "Confirm vendor contact phone number.",
    "VENDOR_ADDRESS_MISMATCH": "Confirm vendor address details.",
    "VENDOR_BANK_ACCOUNT_MISMATCH": "Confirm vendor bank account details.",
    "VENDOR_IFSC_MISMATCH": "Confirm vendor IFSC details.",
    "VENDOR_BANK_NAME_MISMATCH": "Confirm vendor bank name.",
    "UNIT_PRICE_MISMATCH": "Confirm unit price details.",
    "UNIT_PRICE_VARIANCE": "Confirm unit price details.",
    "LINE_TOTAL_MISMATCH": "Confirm line amount details.",
    "ALLOCATION_AMOUNT_MISMATCH": "Confirm allocated amount details.",
    "TOTAL_AMOUNT_MISMATCH": "Confirm invoice amount.",
    "SUBTOTAL_MISMATCH": "Confirm invoice subtotal.",
    "INVOICE_TAX_MISMATCH": "Confirm invoice tax amount.",
    "LINE_TAX_MISMATCH": "Confirm line tax amounts.",
    "DISCOUNT_AMOUNT_MISMATCH": "Confirm discount details.",
    "DUPLICATE_INVOICE_NUMBER": "Confirm invoice number uniqueness.",
    "POTENTIAL_DUPLICATE_INVOICE": "Confirm whether this is a duplicate submission.",
    "QUANTITY_EXCEEDS_ORDERED": "Confirm billed quantities.",
    "QUANTITY_EXCEEDS_REMAINING": "Confirm billed quantities.",
    "MISSING_PO_COVERAGE": "Confirm purchase order coverage for all line items.",
    "PO_RECOVERED": "Confirm the correct purchase order reference.",
    "UNMATCHED_LINE_ITEM": (
        "Confirm how each invoiced line item maps to purchase order lines."
    ),
    "AMBIGUOUS_LINE_MATCH": (
        "Contact the vendor to confirm how many units should be billed against "
        "each purchase order, then select the matching allocation plan."
    ),
    "INVALID_ALLOCATION": (
        "Confirm billed quantities and how they map to purchase order lines."
    ),
    "PO_AMBIGUOUS": "Confirm which purchase order applies to this invoice.",
    "PO_UNRESOLVED": "Confirm the purchase order reference for this invoice.",
}

LINE_ITEM_MAPPING_ISSUE_CODES = frozenset(
    {
        "MISSING_PO_COVERAGE",
        "UNMATCHED_LINE_ITEM",
        "AMBIGUOUS_LINE_MATCH",
        "QUANTITY_EXCEEDS_ORDERED",
        "QUANTITY_EXCEEDS_REMAINING",
        "INVALID_ALLOCATION",
    },
)

PO_REFERENCE_RECOVERY_CODES = frozenset(
    {
        "PO_RECOVERED",
        "PO_MISSING",
        "INVALID_PO_REFERENCE",
    },
)


def recovery_message_for_issue(
    issue_code: str,
    metadata: dict[str, object] | None = None,
) -> str:
    base_message = RECOVERY_MESSAGES.get(
        issue_code,
        "A validation issue was automatically resolved by the system.",
    )
    resolved_po_numbers = _resolved_po_numbers_from_metadata(
        metadata,
    )

    if not resolved_po_numbers:
        return base_message

    po_list = ", ".join(
        resolved_po_numbers,
    )

    if issue_code == "PO_MISSING":
        return (
            "The invoice did not include a purchase order number. "
            f"The system matched it to {po_list}."
        )

    if issue_code == "INVALID_PO_REFERENCE":
        return (
            "The purchase order number on the invoice did not match "
            "the billed line items. "
            f"The system matched the invoice to {po_list}."
        )

    return (
        f"{base_message.rstrip('.')}. "
        f"Matched purchase order(s): {po_list}."
    )


def waived_message_for_issue(
    issue_code: str,
) -> str:
    return WAIVED_MESSAGES.get(
        issue_code,
        "A validation issue was waived to allow processing to continue.",
    )


def _resolved_po_numbers_from_metadata(
    metadata: dict[str, object] | None,
) -> list[str]:
    if not metadata:
        return []

    resolved_po_numbers = metadata.get(
        "resolved_po_numbers",
    )

    if not isinstance(
        resolved_po_numbers,
        list,
    ):
        return []

    return [
        str(po_number)
        for po_number in resolved_po_numbers
        if po_number is not None
    ]


def open_issue_message_for_issue(
    issue_code: str,
) -> str:
    return OPEN_ISSUE_MESSAGES.get(
        issue_code,
        "A validation finding requires finance review.",
    )


def clarification_topic_for_issue(
    issue_code: str,
) -> str | None:
    return VENDOR_CLARIFICATION_TOPICS.get(
        issue_code,
    )


def _format_resolved_po_reference(
    resolved_po_numbers: list[str],
) -> str:
    if not resolved_po_numbers:
        return "candidate purchase order(s)"

    if len(resolved_po_numbers) == 1:
        return resolved_po_numbers[0]

    return ", ".join(
        resolved_po_numbers,
    )


def _line_mapping_issue_detail(
    open_issue_codes: set[str],
) -> str:
    if "AMBIGUOUS_LINE_MATCH" in open_issue_codes:
        return (
            "multiple valid line-to-PO mappings were found and "
            "the system cannot choose one automatically"
        )

    if "UNMATCHED_LINE_ITEM" in open_issue_codes:
        return (
            "the billed quantities or line details could not be "
            "fully matched to available PO lines"
        )

    if "MISSING_PO_COVERAGE" in open_issue_codes:
        return "one or more invoice lines lack matching PO line coverage"

    if {
        "QUANTITY_EXCEEDS_ORDERED",
        "QUANTITY_EXCEEDS_REMAINING",
        "INVALID_ALLOCATION",
    } & open_issue_codes:
        return (
            "billed quantities do not align with the remaining "
            "purchase order quantities"
        )

    return "line item mapping could not be confirmed"


def build_open_issue_messages(
    open_issue_codes: list[str],
    resolved_po_numbers: list[str] | None = None,
) -> list[str]:
    codes = {
        code
        for code in open_issue_codes
        if code
    }
    messages: list[str] = []
    consumed: set[str] = set()
    po_reference = _format_resolved_po_reference(
        resolved_po_numbers or [],
    )

    if codes & PO_REFERENCE_RECOVERY_CODES and codes & LINE_ITEM_MAPPING_ISSUE_CODES:
        messages.append(
            "A purchase order candidate was recovered automatically "
            f"({po_reference}), but invoice line items could not be "
            f"mapped to PO lines because "
            f"{_line_mapping_issue_detail(codes)}.",
        )
        consumed |= PO_REFERENCE_RECOVERY_CODES | LINE_ITEM_MAPPING_ISSUE_CODES
    elif "AMBIGUOUS_LINE_MATCH" in codes:
        messages.append(
            "Multiple valid line-to-PO allocation plans were found. "
            "Review the proposed mappings and confirm the correct plan."
        )
        consumed.add(
            "AMBIGUOUS_LINE_MATCH",
        )
    elif "UNMATCHED_LINE_ITEM" in codes:
        messages.append(
            "Invoice line items could not be fully matched to purchase "
            "order lines using the recovered PO candidate(s)."
        )
        consumed.add(
            "UNMATCHED_LINE_ITEM",
        )

    for issue_code in open_issue_codes:
        if issue_code in consumed:
            continue

        messages.append(
            open_issue_message_for_issue(
                issue_code,
            ),
        )

    return deduplicate_messages(
        messages,
    )


def build_vendor_clarification_messages(
    open_issue_codes: list[str],
    resolved_po_numbers: list[str] | None = None,
) -> list[str]:
    codes = {
        code
        for code in open_issue_codes
        if code
    }
    messages: list[str] = []
    consumed: set[str] = set()
    po_reference = _format_resolved_po_reference(
        resolved_po_numbers or [],
    )

    if codes & PO_REFERENCE_RECOVERY_CODES and codes & LINE_ITEM_MAPPING_ISSUE_CODES:
        messages.append(
            "Confirm the correct purchase order reference "
            f"({po_reference}) and how each invoiced line item should "
            f"map to PO lines, because "
            f"{_line_mapping_issue_detail(codes)}."
        )
        consumed |= PO_REFERENCE_RECOVERY_CODES | LINE_ITEM_MAPPING_ISSUE_CODES
    elif "AMBIGUOUS_LINE_MATCH" in codes:
        messages.append(
            "Confirm which purchase order line each invoiced item "
            "should be billed against. Multiple valid mappings were found."
        )
        consumed.add(
            "AMBIGUOUS_LINE_MATCH",
        )
    elif "UNMATCHED_LINE_ITEM" in codes:
        messages.append(
            "Confirm how each invoiced line item maps to purchase "
            "order lines. The billed quantities could not be fully matched."
        )
        consumed.add(
            "UNMATCHED_LINE_ITEM",
        )

    for issue_code in open_issue_codes:
        if issue_code in consumed:
            continue

        topic = clarification_topic_for_issue(
            issue_code,
        )

        if topic is None:
            continue

        messages.append(
            topic,
        )

    return deduplicate_messages(
        messages,
    )


def deduplicate_messages(
    messages: list[str],
) -> list[str]:
    seen: set[str] = set()
    unique_messages: list[str] = []

    for message in messages:
        normalized = message.strip()

        if not normalized or normalized in seen:
            continue

        seen.add(
            normalized,
        )
        unique_messages.append(
            normalized,
        )

    return unique_messages
