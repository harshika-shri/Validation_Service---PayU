from __future__ import annotations

import re


def normalize_text(
    value: str,
) -> str:
    collapsed = re.sub(
        r"\s+",
        " ",
        value.strip(),
    )

    return collapsed.casefold()


def normalize_company_name_for_exact_match(
    value: str,
) -> str:
    return normalize_text(
        value,
    )


def normalize_gstin(
    value: str,
) -> str:
    return re.sub(
        r"\s+",
        "",
        value.strip(),
    ).upper()


def normalize_pan(
    value: str,
) -> str:
    return re.sub(
        r"\s+",
        "",
        value.strip(),
    ).upper()


def normalize_email(
    value: str,
) -> str:
    return value.strip().casefold()


def normalize_phone(
    value: str,
) -> str:
    digits = re.sub(
        r"\D",
        "",
        value,
    )

    if len(digits) > 10:
        return digits[-10:]

    return digits


def normalize_address(
    value: str,
) -> str:
    collapsed = re.sub(
        r"\s+",
        " ",
        value.strip(),
    )

    return collapsed


def normalize_bank_account(
    value: str,
) -> str:
    return re.sub(
        r"\D",
        "",
        value.strip(),
    )


def normalize_ifsc(
    value: str,
) -> str:
    return re.sub(
        r"\s+",
        "",
        value.strip(),
    ).upper()


def normalize_bank_name(
    value: str,
) -> str:
    return normalize_text(
        value,
    )


def has_text(
    value: str | None,
) -> bool:
    return value is not None and bool(
        value.strip(),
    )
