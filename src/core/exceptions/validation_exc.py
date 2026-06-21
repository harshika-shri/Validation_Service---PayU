from __future__ import annotations

from uuid import UUID

from src.core.exceptions.base_exc import AppException


class InvoiceNotFoundError(AppException):
    def __init__(
        self,
        invoice_id: UUID,
    ) -> None:
        super().__init__(
            detail=f"Invoice not found: {invoice_id}",
            status_code=404,
            error_code="INVOICE_NOT_FOUND",
        )
