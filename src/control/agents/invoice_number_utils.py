from __future__ import annotations

import re
from uuid import UUID

INVOICE_NUMBER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\bINV[-\s]?[A-Za-z0-9]+\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bINVOICE[-\s]?[A-Za-z0-9]+\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bBILL[-\s]?[A-Za-z0-9]+\b",
        re.IGNORECASE,
    ),
)


def extract_invoice_number(
    text: str | None,
) -> str | None:
    if not text:
        return None

    for pattern in INVOICE_NUMBER_PATTERNS:
        match = pattern.search(text)

        if match is not None:
            return match.group(0).upper()

    return None


def generate_auto_invoice_number(
    invoice_id: UUID,
) -> str:
    short_uuid = (
        str(invoice_id)
        .replace(
            "-",
            "",
        )[:6]
        .upper()
    )

    return f"AUTO-INV-{short_uuid}"


def is_generated_invoice_number(
    invoice_number: str | None,
) -> bool:
    if invoice_number is None:
        return False

    return invoice_number.strip().upper().startswith(
        "AUTO-INV-",
    )
