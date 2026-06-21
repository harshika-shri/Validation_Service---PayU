from __future__ import annotations

import re


def normalize_item_code(
    value: str,
) -> str:
    return re.sub(
        r"\s+",
        "",
        value.strip(),
    ).casefold()


def normalize_item_description(
    value: str,
) -> str:
    collapsed = re.sub(
        r"\s+",
        " ",
        value.strip(),
    )

    return collapsed.casefold()


def has_text(
    value: str | None,
) -> bool:
    return value is not None and bool(
        value.strip(),
    )
