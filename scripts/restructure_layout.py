"""One-off layout restructure: agents + repositories grouped by graph node."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src"

AGENT_MOVES: dict[str, str] = {
    "control/agents/invoice_header_resolution.py": "control/agents/invoice_header_resolution/invoice_header_resolution.py",
    "control/agents/invoice_number_utils.py": "control/agents/invoice_header_resolution/invoice_number_utils.py",
    "control/agents/buyer_company_validation.py": "control/agents/company_resolution/company_resolution.py",
    "control/agents/vendor_resolution.py": "control/agents/vendor_resolution/vendor_resolution.py",
    "control/agents/po_resolution.py": "control/agents/po_resolution/po_resolution.py",
    "control/agents/po_line_matcher.py": "control/agents/po_resolution/po_line_matcher.py",
    "control/agents/po_coverage_search.py": "control/agents/po_resolution/po_coverage_search.py",
    "control/agents/line_allocation_search.py": "control/agents/po_resolution/line_allocation_search.py",
    "control/agents/line_item_validation.py": "control/agents/line_item_validation/line_item_validation.py",
    "control/agents/amount_validation.py": "control/agents/amount_validation/amount_validation.py",
    "control/agents/duplicate_detection.py": "control/agents/duplicate_detection/duplicate_detection.py",
    "control/agents/final_decision.py": "control/agents/final_decision/final_decision.py",
    "control/agents/review_summary_generation.py": "control/agents/review_summary_generation/review_summary_generation.py",
}

REPO_MOVES: dict[str, str] = {
    "data/repositories/validation_issue_repository.py": "data/repositories/shared/validation_issue_repository.py",
    "data/repositories/invoice_repository.py": "data/repositories/invoice_header_resolution/invoice_repository.py",
    "data/repositories/invoice_email_repository.py": "data/repositories/invoice_header_resolution/invoice_email_repository.py",
    "data/repositories/company_repository.py": "data/repositories/company_resolution/company_repository.py",
    "data/repositories/vendor_repository.py": "data/repositories/vendor_resolution/vendor_repository.py",
    "data/repositories/invoice_extracted_vendor_repository.py": "data/repositories/vendor_resolution/invoice_extracted_vendor_repository.py",
    "data/repositories/purchase_order_repository.py": "data/repositories/po_resolution/purchase_order_repository.py",
    "data/repositories/invoice_po_mapping_repository.py": "data/repositories/po_resolution/invoice_po_mapping_repository.py",
    "data/repositories/invoice_po_resolution_repository.py": "data/repositories/po_resolution/invoice_po_resolution_repository.py",
    "data/repositories/po_line_item_repository.py": "data/repositories/po_resolution/po_line_item_repository.py",
    "data/repositories/po_line_quantity_repository.py": "data/repositories/po_resolution/po_line_quantity_repository.py",
    "data/repositories/invoice_line_po_allocation_repository.py": "data/repositories/po_resolution/invoice_line_po_allocation_repository.py",
    "data/repositories/invoice_line_item_repository.py": "data/repositories/line_item_validation/invoice_line_item_repository.py",
    "data/repositories/invoice_amount_repository.py": "data/repositories/amount_validation/invoice_amount_repository.py",
    "data/repositories/invoice_line_amount_repository.py": "data/repositories/amount_validation/invoice_line_amount_repository.py",
    "data/repositories/duplicate_detection_repository.py": "data/repositories/duplicate_detection/duplicate_detection_repository.py",
    "data/repositories/issue_decision_rules_repository.py": "data/repositories/final_decision/issue_decision_rules_repository.py",
    "data/repositories/invoice_review_summary_repository.py": "data/repositories/review_summary_generation/invoice_review_summary_repository.py",
}

IMPORT_REPLACEMENTS: list[tuple[str, str]] = [
    # repositories (longer module names first)
    (
        "from src.data.repositories.invoice_line_po_allocation_repository import",
        "from src.data.repositories.po_resolution.invoice_line_po_allocation_repository import",
    ),
    (
        "from src.data.repositories.invoice_line_amount_repository import",
        "from src.data.repositories.amount_validation.invoice_line_amount_repository import",
    ),
    (
        "from src.data.repositories.invoice_line_item_repository import",
        "from src.data.repositories.line_item_validation.invoice_line_item_repository import",
    ),
    (
        "from src.data.repositories.invoice_extracted_vendor_repository import",
        "from src.data.repositories.vendor_resolution.invoice_extracted_vendor_repository import",
    ),
    (
        "from src.data.repositories.invoice_po_resolution_repository import",
        "from src.data.repositories.po_resolution.invoice_po_resolution_repository import",
    ),
    (
        "from src.data.repositories.invoice_po_mapping_repository import",
        "from src.data.repositories.po_resolution.invoice_po_mapping_repository import",
    ),
    (
        "from src.data.repositories.invoice_review_summary_repository import",
        "from src.data.repositories.review_summary_generation.invoice_review_summary_repository import",
    ),
    (
        "from src.data.repositories.invoice_amount_repository import",
        "from src.data.repositories.amount_validation.invoice_amount_repository import",
    ),
    (
        "from src.data.repositories.invoice_email_repository import",
        "from src.data.repositories.invoice_header_resolution.invoice_email_repository import",
    ),
    (
        "from src.data.repositories.invoice_repository import",
        "from src.data.repositories.invoice_header_resolution.invoice_repository import",
    ),
    (
        "from src.data.repositories.duplicate_detection_repository import",
        "from src.data.repositories.duplicate_detection.duplicate_detection_repository import",
    ),
    (
        "from src.data.repositories.issue_decision_rules_repository import",
        "from src.data.repositories.final_decision.issue_decision_rules_repository import",
    ),
    (
        "from src.data.repositories.po_line_quantity_repository import",
        "from src.data.repositories.po_resolution.po_line_quantity_repository import",
    ),
    (
        "from src.data.repositories.po_line_item_repository import",
        "from src.data.repositories.po_resolution.po_line_item_repository import",
    ),
    (
        "from src.data.repositories.purchase_order_repository import",
        "from src.data.repositories.po_resolution.purchase_order_repository import",
    ),
    (
        "from src.data.repositories.validation_issue_repository import",
        "from src.data.repositories.shared.validation_issue_repository import",
    ),
    (
        "from src.data.repositories.company_repository import",
        "from src.data.repositories.company_resolution.company_repository import",
    ),
    (
        "from src.data.repositories.vendor_repository import",
        "from src.data.repositories.vendor_resolution.vendor_repository import",
    ),
    # agent helpers
    (
        "from src.control.agents.line_allocation_search import",
        "from src.control.agents.po_resolution.line_allocation_search import",
    ),
    (
        "from src.control.agents.po_coverage_search import",
        "from src.control.agents.po_resolution.po_coverage_search import",
    ),
    (
        "from src.control.agents.po_line_matcher import",
        "from src.control.agents.po_resolution.po_line_matcher import",
    ),
    (
        "from src.control.agents.invoice_number_utils import",
        "from src.control.agents.invoice_header_resolution.invoice_number_utils import",
    ),
    # agent nodes
    (
        "from src.control.agents.buyer_company_validation import",
        "from src.control.agents.company_resolution.company_resolution import",
    ),
    (
        "from src.control.agents.review_summary_generation import",
        "from src.control.agents.review_summary_generation.review_summary_generation import",
    ),
    (
        "from src.control.agents.invoice_header_resolution import",
        "from src.control.agents.invoice_header_resolution.invoice_header_resolution import",
    ),
    (
        "from src.control.agents.line_item_validation import",
        "from src.control.agents.line_item_validation.line_item_validation import",
    ),
    (
        "from src.control.agents.duplicate_detection import",
        "from src.control.agents.duplicate_detection.duplicate_detection import",
    ),
    (
        "from src.control.agents.amount_validation import",
        "from src.control.agents.amount_validation.amount_validation import",
    ),
    (
        "from src.control.agents.vendor_resolution import",
        "from src.control.agents.vendor_resolution.vendor_resolution import",
    ),
    (
        "from src.control.agents.final_decision import",
        "from src.control.agents.final_decision.final_decision import",
    ),
    (
        "from src.control.agents.po_resolution import",
        "from src.control.agents.po_resolution.po_resolution import",
    ),
]


def move_files(moves: dict[str, str]) -> None:
    for source_rel, dest_rel in moves.items():
        source = ROOT / source_rel
        dest = ROOT / dest_rel
        if not source.exists():
            if dest.exists():
                continue
            raise FileNotFoundError(source)
        dest.parent.mkdir(parents=True, exist_ok=True)
        source.rename(dest)
        print(f"moved {source_rel} -> {dest_rel}")


def apply_import_replacements(content: str) -> str:
    for old, new in IMPORT_REPLACEMENTS:
        content = content.replace(old, new)
    return content


def update_all_python_files() -> None:
    for path in ROOT.rglob("*.py"):
        if path.name == "restructure_layout.py":
            continue
        text = path.read_text(encoding="utf-8")
        updated = apply_import_replacements(text)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            print(f"updated imports in {path.relative_to(ROOT)}")


def main() -> None:
    move_files(REPO_MOVES)
    move_files(AGENT_MOVES)
    update_all_python_files()
    print("done")


if __name__ == "__main__":
    main()
