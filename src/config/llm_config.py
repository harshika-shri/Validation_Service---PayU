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
    "the same legal vendor entity.\n\n"
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

FUZZY_MATCH_PROMPT = """You are validating invoice line items against purchase order line items.

Your task is NOT to determine whether the descriptions belong to the same product category.

Your task is to determine whether they refer to the SAME ordered item with sufficient certainty for financial validation.

MATCH ONLY WHEN THERE IS POSITIVE EVIDENCE.

Never match based solely on a generic category.

---

## MATCH RULES

Return MATCH when:

* Same product name
* Same model number
* Same product family
* Same item with minor wording differences
* Same item with additional specifications
* Same item with abbreviations

Examples:

ThinkPad E14
vs
Lenovo ThinkPad E14 Gen5

→ MATCH

Samsung SSD 1TB
vs
Samsung 1 TB Solid State Drive

→ MATCH

HP LaserJet Printer
vs
HP LaserJet Pro Printer

→ MATCH

---

## NO MATCH RULES

Return NO MATCH when:

The invoice description is too generic.

Examples:

Laptop
vs
Lenovo ThinkPad E14 Gen5 Laptop

→ NO MATCH

Monitor
vs
Samsung 24 Inch Monitor

→ NO MATCH

Printer
vs
HP LaserJet Pro Printer

→ NO MATCH

SSD
vs
Samsung SSD 1TB

→ NO MATCH

Generic descriptions do not provide enough evidence.

---

## CATEGORY RULE

Belonging to the same category is NOT sufficient.

Examples:

Laptop
vs
ThinkPad Laptop

→ NO MATCH

Monitor
vs
Samsung Monitor

→ NO MATCH

SSD
vs
Samsung SSD

→ NO MATCH

---

## BRAND RULE

Same brand alone is NOT sufficient.

Samsung Monitor
vs
Samsung SSD

→ NO MATCH

Lenovo Laptop
vs
Lenovo Monitor

→ NO MATCH

---

## CONFIDENCE RULE

Confidence > 0.90

Strong evidence of same item.

Confidence 0.75 - 0.90

Some similarity but not enough for automatic matching.

Confidence < 0.75

Insufficient evidence.

If there is insufficient evidence, return:

{{
"is_match": false
}}

---

## OUTPUT

Return JSON only:

{{
"is_match": true,
"confidence": 0.95,
"reason": "short explanation"
}}

---

Invoice Line Description:
{extracted}

PO Line Description:
{master}
"""

LINE_ITEM_MATCH_PROMPT = FUZZY_MATCH_PROMPT

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
