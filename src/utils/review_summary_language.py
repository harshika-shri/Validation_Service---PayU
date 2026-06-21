from __future__ import annotations

RECOVERY_MESSAGES: dict[str, str] = {
    "MISSING_INVOICE_NUMBER": (
        "Missing invoice number was generated automatically by the system."
    ),
    "VENDOR_NOT_FOUND": (
        "Vendor was successfully identified after initial lookup "
        "did not find a direct match."
    ),
    "PO_NOT_FOUND": (
        "The invoice did not include a purchase order number. "
        "The system automatically matched the invoice to the "
        "correct purchase order(s)."
    ),
    "INVALID_PO_REFERENCE": (
        "The purchase order number on the invoice did not match "
        "the line items billed. The system identified the correct "
        "purchase order(s) from available orders."
    ),
}

OPEN_ISSUE_MESSAGES: dict[str, str] = {
    "MISSING_INVOICE_NUMBER": (
        "Invoice number is missing on the submitted invoice."
    ),
    "VENDOR_NOT_FOUND": (
        "Vendor could not be matched to a vendor master record."
    ),
    "PO_NOT_FOUND": (
        "Referenced purchase order number was not found."
    ),
    "INVALID_PO_REFERENCE": (
        "Referenced purchase order does not match resolved coverage."
    ),
    "COMPANY_NAME_MISMATCH": (
        "Buyer company name differs from the company master record."
    ),
    "COMPANY_GSTIN_MISMATCH": (
        "Buyer GSTIN differs from the company master record."
    ),
    "COMPANY_PAN_MISMATCH": (
        "Buyer PAN differs from the company master record."
    ),
    "COMPANY_ADDRESS_MISMATCH": (
        "Buyer billing address differs from the company master record."
    ),
    "COMPANY_SHIPPING_ADDRESS_MISMATCH": (
        "Buyer shipping address differs from the company master record."
    ),
    "COMPANY_EMAIL_MISMATCH": (
        "Buyer email differs from the company master record."
    ),
    "COMPANY_PHONE_MISMATCH": (
        "Buyer phone number differs from the company master record."
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
        "Vendor GSTIN differs from the vendor master record."
    ),
    "VENDOR_PHONE_MISMATCH": (
        "Vendor phone number differs from the vendor master record."
    ),
    "VENDOR_ADDRESS_MISMATCH": (
        "Vendor address differs from the vendor master record."
    ),
    "VENDOR_BANK_ACCOUNT_MISMATCH": (
        "Vendor bank account differs from the vendor master record."
    ),
    "VENDOR_IFSC_MISMATCH": (
        "Vendor IFSC code differs from the vendor master record."
    ),
    "VENDOR_BANK_NAME_MISMATCH": (
        "Vendor bank name differs from the vendor master record."
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
        "Purchase order coverage could not be resolved for this invoice."
    ),
    "PO_AMBIGUOUS": (
        "Multiple valid purchase order combinations were found."
    ),
    "PO_VENDOR_CONFLICT": (
        "Resolved purchase order belongs to a different vendor."
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
    "COMPANY_NAME_MISMATCH": "Confirm buyer company details.",
    "COMPANY_GSTIN_MISMATCH": "Confirm GSTIN details.",
    "COMPANY_PAN_MISMATCH": "Confirm PAN details.",
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
}


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

    if issue_code == "PO_NOT_FOUND":
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
