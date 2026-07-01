from src.utils.po_number_utils import (
    normalize_po_number_for_lookup,
    parse_po_number_header_value,
    parse_po_numbers,
)


def test_parse_po_numbers_splits_comma_separated_values() -> None:
    assert parse_po_numbers(
        ["PO_ASUS_03, PO_ASUS_02"],
    ) == [
        "PO_ASUS_03",
        "PO_ASUS_02",
    ]


def test_parse_po_numbers_deduplicates_case_insensitive() -> None:
    assert parse_po_numbers(
        [
            "PO_ASUS_03",
            "po_asus_03",
        ],
    ) == [
        "PO_ASUS_03",
    ]


def test_parse_po_number_header_value_returns_none_for_empty() -> None:
    assert (
        parse_po_number_header_value(
            None,
        )
        is None
    )
    assert (
        parse_po_number_header_value(
            "n/a",
        )
        is None
    )


def test_normalize_po_number_for_lookup_trims_whitespace() -> None:
    assert (
        normalize_po_number_for_lookup(
            "  PO_CM_212  ",
        )
        == "PO_CM_212"
    )
    assert (
        normalize_po_number_for_lookup(
            "PO  CM   212",
        )
        == "PO CM 212"
    )
