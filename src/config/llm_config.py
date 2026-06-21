COMPANY_NAME_MATCH_PROMPT = (
    "You are validating whether two company names refer to "
    "the same legal entity.\n\n"
    "Consider abbreviations, Pvt Ltd vs Private Limited, "
    "punctuation differences, OCR errors, and minor spelling "
    "mistakes as potential matches.\n\n"
    "Extracted Company Name:\n"
    "{extracted}\n\n"
    "Master Company Name:\n"
    "{master}\n\n"
    'Return JSON only:\n'
    '{{"is_match": true, "reason": "brief explanation"}}\n'
    'or\n'
    '{{"is_match": false, "reason": "brief explanation"}}'
)

ADDRESS_MATCH_PROMPT = (
    "You are validating whether two addresses refer to "
    "the same physical location.\n\n"
    "Consider formatting differences, abbreviations, OCR errors, "
    "line breaks, and punctuation differences as potential matches.\n\n"
    "Extracted Address:\n"
    "{extracted}\n\n"
    "Master Address:\n"
    "{master}\n\n"
    'Return JSON only:\n'
    '{{"is_match": true, "reason": "brief explanation"}}\n'
    'or\n'
    '{{"is_match": false, "reason": "brief explanation"}}'
)

VENDOR_NAME_MATCH_PROMPT = (
    "You are validating whether two vendor names refer to "
    "the same organization.\n\n"
    "Consider abbreviations, Pvt Ltd vs Private Limited, "
    "punctuation differences, OCR errors, spacing differences, "
    "and minor spelling mistakes as potential matches.\n\n"
    "Extracted Vendor Name:\n"
    "{extracted}\n\n"
    "Vendor Master Name:\n"
    "{master}\n\n"
    'Return JSON only:\n'
    '{{"is_match": true, "reason": "brief explanation"}}\n'
    'or\n'
    '{{"is_match": false, "reason": "brief explanation"}}'
)

LINE_ITEM_MATCH_PROMPT = (
    "You are validating whether two product line descriptions "
    "refer to the same item.\n\n"
    "Consider abbreviations, OCR errors, spacing differences, "
    "and minor spelling mistakes as potential matches.\n\n"
    "Invoice Line Description:\n"
    "{extracted}\n\n"
    "PO Line Description:\n"
    "{master}\n\n"
    'Return JSON only:\n'
    '{{"is_match": true, "reason": "brief explanation"}}\n'
    'or\n'
    '{{"is_match": false, "reason": "brief explanation"}}'
)

REVIEW_SUMMARY_PROMPT = (
    "Generate a concise finance review summary.\n\n"
    "Rules:\n"
    "- Maximum 5 sentences.\n"
    "- Use plain business language that a finance reviewer can "
    "understand immediately.\n"
    "- Do not mention issue codes or internal system terms.\n"
    "- State the final decision clearly in the first sentence.\n"
    "- If system_recoveries is non-empty, explain what was missing "
    "or incorrect and which purchase order(s) the system matched.\n"
    "- If open_issues is empty, say clearly that no unresolved "
    "validation findings remain.\n"
    "- If vendor_clarifications is empty, say clearly that no "
    "vendor clarification is required.\n"
    "- Never say vendor clarification is required when "
    "vendor_clarifications is empty.\n"
    "- Never contradict the decision in the input.\n"
    "- Do not recommend next actions.\n\n"
    "Input:\n"
    "{payload}\n\n"
    "Return plain text only."
)
