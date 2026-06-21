from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

_CHARGE_PATTERNS: dict[str, re.Pattern[str]] = {
    "handling": re.compile(
        r"handling(?:\s+fee)?[:\s]+(?:rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)",
        re.IGNORECASE,
    ),
    "freight": re.compile(
        r"freight(?:\s+charge)?[:\s]+(?:rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)",
        re.IGNORECASE,
    ),
    "shipping": re.compile(
        r"shipping(?:\s+charge)?[:\s]+(?:rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)",
        re.IGNORECASE,
    ),
    "processing": re.compile(
        r"processing(?:\s+fee)?[:\s]+(?:rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)",
        re.IGNORECASE,
    ),
    "misc": re.compile(
        r"(?:misc(?:ellaneous)?|other)(?:\s+charge)?[:\s]+(?:rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)",
        re.IGNORECASE,
    ),
}


def amounts_equal(
    expected: Decimal,
    actual: Decimal,
    *,
    tolerance: Decimal,
) -> bool:
    return abs(
        expected - actual,
    ) <= tolerance


def is_within_variance(
    expected: Decimal,
    actual: Decimal,
    *,
    tolerance: Decimal,
) -> bool:
    if expected == actual:
        return True

    if expected == Decimal(0):
        return actual == Decimal(0)

    difference = abs(
        expected - actual,
    )

    if difference <= tolerance:
        return True

    return difference / abs(
        expected,
    ) <= tolerance


def parse_charges_from_notes(
    notes: str | None,
) -> dict[str, Decimal]:
    if not notes or not notes.strip():
        return {}

    charges: dict[str, Decimal] = {}

    for charge_type, pattern in _CHARGE_PATTERNS.items():
        match = pattern.search(
            notes,
        )

        if match is None:
            continue

        amount = _parse_amount(
            match.group(1),
        )

        if amount is not None and amount > 0:
            charges[charge_type] = amount

    return charges


def sum_decimal_values(
    values: list[Decimal | None],
) -> Decimal:
    total = Decimal(0)

    for value in values:
        if value is not None:
            total += value

    return total.quantize(
        Decimal("0.01"),
    )


def _parse_amount(
    raw_value: str,
) -> Decimal | None:
    cleaned = raw_value.replace(
        ",",
        "",
    ).strip()

    try:
        return Decimal(
            cleaned,
        ).quantize(
            Decimal("0.01"),
        )
    except Exception:
        return None


def decimal_to_str(
    value: Decimal | None,
) -> str | None:
    if value is None:
        return None

    return str(
        value.quantize(
            Decimal("0.01"),
        ),
    )


def has_positive_amount(
    value: Decimal | None,
) -> bool:
    return value is not None and value > 0


def coerce_decimal(
    value: Any,
) -> Decimal | None:
    if value is None:
        return None

    if isinstance(
        value,
        Decimal,
    ):
        return value.quantize(
            Decimal("0.01"),
        )

    try:
        return Decimal(
            str(value),
        ).quantize(
            Decimal("0.01"),
        )
    except Exception:
        return None
