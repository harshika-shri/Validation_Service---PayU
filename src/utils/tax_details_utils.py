from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


def normalize_tax_details(
    tax_details: Any,
) -> dict[str, Any] | None:
    if tax_details is None:
        return None

    if isinstance(
        tax_details,
        dict,
    ):
        return _normalize_tax_dict(
            tax_details,
        )

    if isinstance(
        tax_details,
        list,
    ):
        normalized: dict[str, Any] = {}

        for index, item in enumerate(
            tax_details,
        ):
            if isinstance(
                item,
                dict,
            ):
                tax_name = (
                    item.get("tax_name")
                    or item.get("name")
                    or item.get("type")
                )
                tax_value = (
                    item.get("tax_value")
                    or item.get("value")
                    or item.get("rate")
                    or item.get("amount")
                )

                if tax_name is not None:
                    normalized[str(tax_name)] = tax_value
                elif tax_value is not None:
                    normalized[f"tax_{index + 1}"] = tax_value

                continue

            if item is not None:
                normalized[f"tax_{index + 1}"] = item

        return normalized or None

    return {
        "value": tax_details,
    }


def sum_tax_amounts(
    tax_details: dict[str, Any] | None,
    taxable_base: Decimal,
) -> Decimal:
    if not tax_details:
        return Decimal(0)

    total = Decimal(0)

    for key, value in tax_details.items():
        amount = _tax_entry_amount(
            key=str(key),
            value=value,
            taxable_base=taxable_base,
        )

        if amount is not None:
            total += amount

    return total.quantize(
        Decimal("0.01"),
    )


def compute_invoice_line_tax_total(
    invoice_lines: list[Any],
    *,
    header_tax_amount: Decimal | None,
    quantity_attr: str = "quantity_billed",
    unit_price_attr: str = "unit_price",
    discount_attr: str = "discount_amount",
    tax_details_attr: str = "tax_details",
) -> Decimal:
    if not invoice_lines:
        return Decimal(0)

    explicit_total = Decimal(0)
    base_without_details = Decimal(0)

    for line in invoice_lines:
        quantity = getattr(
            line,
            quantity_attr,
        )
        unit_price = getattr(
            line,
            unit_price_attr,
        )
        discount = getattr(
            line,
            discount_attr,
        ) or Decimal(0)
        taxable_base = (
            quantity * unit_price - discount
        ).quantize(
            Decimal("0.01"),
        )
        tax_details = normalize_tax_details(
            getattr(
                line,
                tax_details_attr,
            ),
        )

        if tax_details:
            explicit_total += sum_tax_amounts(
                tax_details,
                taxable_base,
            )
        else:
            base_without_details += taxable_base

    if header_tax_amount is None:
        return explicit_total.quantize(
            Decimal("0.01"),
        )

    if base_without_details <= 0:
        return explicit_total.quantize(
            Decimal("0.01"),
        )

    if explicit_total >= header_tax_amount:
        return explicit_total.quantize(
            Decimal("0.01"),
        )

    return header_tax_amount.quantize(
        Decimal("0.01"),
    )


def _normalize_tax_dict(
    tax_details: dict[str, Any],
) -> dict[str, Any]:
    normalized: dict[str, Any] = {}

    for key, value in tax_details.items():
        if value is None:
            continue

        if isinstance(
            value,
            dict,
        ):
            tax_name = (
                value.get("tax_name")
                or value.get("name")
                or key
            )
            tax_value = (
                value.get("tax_value")
                or value.get("value")
                or value.get("rate")
                or value.get("amount")
            )
            normalized[str(tax_name)] = tax_value
            continue

        normalized[str(key)] = value

    return normalized


def _tax_entry_amount(
    key: str,
    value: Any,
    taxable_base: Decimal,
) -> Decimal | None:
    numeric = _to_decimal(
        value,
    )

    if numeric is None:
        return None

    key_lower = key.casefold()

    if (
        "rate" in key_lower
        or key_lower.endswith("_pct")
        or key_lower.endswith("%")
    ):
        return taxable_base * numeric / Decimal(100)

    if numeric <= Decimal(100) and taxable_base > Decimal(0):
        percent_like_keys = (
            "cgst",
            "sgst",
            "igst",
            "gst",
            "vat",
            "tax",
        )

        if any(
            token in key_lower
            for token in percent_like_keys
        ):
            return taxable_base * numeric / Decimal(100)

    return numeric


def _to_decimal(
    value: Any,
) -> Decimal | None:
    if value is None:
        return None

    if isinstance(
        value,
        Decimal,
    ):
        return value

    try:
        return Decimal(
            str(value).strip(),
        )
    except (InvalidOperation, ValueError):
        return None
