from __future__ import annotations

import re

_INVALID_PO_PLACEHOLDERS = frozenset(
    {
        "---",
        "-",
        "n/a",
        "na",
        "none",
        "null",
        "nil",
    },
)

_PO_NUMBER_SPLIT_PATTERN = re.compile(
    r"[,;/]+",
)


def parse_po_numbers(
    raw_values: object,
) -> list[str]:
    if raw_values is None:
        return []

    if not isinstance(
        raw_values,
        list,
    ):
        return []

    numbers: list[str] = []
    seen: set[str] = set()

    for value in raw_values:
        if value is None:
            continue

        normalized = str(
            value,
        ).strip()

        if not normalized:
            continue

        parts = _PO_NUMBER_SPLIT_PATTERN.split(
            normalized,
        )

        for part in parts:
            po_number = part.strip()

            if (
                not po_number
                or po_number.casefold()
                in _INVALID_PO_PLACEHOLDERS
            ):
                continue

            dedupe_key = po_number.casefold()

            if dedupe_key in seen:
                continue

            seen.add(
                dedupe_key,
            )
            numbers.append(
                po_number,
            )

    return numbers


def normalize_po_number_for_lookup(
    po_number: str,
) -> str:
    return re.sub(
        r"\s+",
        " ",
        po_number.strip(),
    )


def parse_po_number_header_value(
    po_number: str | None,
) -> list[str] | None:
    parsed = parse_po_numbers(
        [po_number]
        if po_number
        else None,
    )

    if not parsed:
        return None

    return parsed
