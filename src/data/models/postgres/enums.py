from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    FINANCE_ASSOCIATE = "finance_associate"
    FINANCE_MANAGER = "finance_manager"


class CompanyStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class VendorStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLACKLISTED = "blacklisted"
    SUSPENDED = "suspended"


class PurchaseOrderStatus(str, Enum):
    OPEN = "open"
    PARTIALLY_PROCESSED = "partially_processed"
    CLOSED = "closed"


class ExtractionStatus(str, Enum):
    PENDING = "pending"
    OCR_PROCESSING = "ocr_processing"
    EXTRACTED = "extracted"
    LOW_CONFIDENCE = "low_confidence"
    HUMAN_REVIEW_NEEDED = "human_review_needed"
    EXTRACTION_APPROVED = "extraction_approved"


class InvoiceStatus(str, Enum):
    UNDER_VALIDATION = "under_validation"
    MATCH_APPROVED = "match_approved"
    MATCH_ISSUES = "match_issues"
    APPROVED_READY_TO_PAY = "approved_ready_to_pay"
    PENDING_ACTION = "pending_action"
    OVERDUE = "overdue"
    PAID = "paid"
    UNDER_REVIEW = "under_review"
    READY_FOR_APPROVAL = "ready_for_approval"
    PARTIALLY_APPROVED = "partially_approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    READY_TO_PAY = "ready_to_pay"


class DisputeStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class CommunicationStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    SENT = "sent"


class IssueType(str, Enum):
    LOW_CONFIDENCE = "low_confidence"
    MISMATCH = "mismatch"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    DUPLICATE = "duplicate"
    INVALID = "invalid"
    WARNING = "warning"


class ValidationIssueStatus(str, Enum):
    OPEN = "open"
    PENDING_REVIEW = "pending_review"
    RESOLVED = "resolved"
    WAIVED = "waived"


class InvoiceValidationDecision(str, Enum):
    APPROVED_AND_READY_TO_PAY = "approved_and_ready_to_pay"
    PARTIAL_APPROVE = "partial_approve"
    REJECT = "reject"


class InvoiceValidationOutcome(str, Enum):
    RESOLVED = "resolved"
    RECOVERED = "recovered"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"
    DUPLICATE = "duplicate"
    APPROVED = "approved"
    PENDING_REVIEW = "pending_review"
    REJECTED = "rejected"


class AllocationMatchType(str, Enum):
    EXACT_CODE = "exact_code"
    LLM_FUZZY = "llm_fuzzy"
    SPLIT = "split"
    MANUAL = "manual"


class AllocationStatus(str, Enum):
    PENDING = "pending"
    COMMITTED = "committed"
    CANCELLED = "cancelled"
    CONFIRMED = "confirmed"


class ValidationFlowOutcome(str, Enum):
    CONTINUE = "continue"
    REROUTE = "reroute"
    HARD_STOP = "hard_stop"


class POResolutionCandidateType(str, Enum):
    RESOLVED = "resolved"
    RECOVERED = "recovered"
    AMBIGUOUS = "ambiguous"
