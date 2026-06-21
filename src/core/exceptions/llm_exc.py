from __future__ import annotations

from src.core.exceptions.base_exc import AppException


class LLMServiceError(AppException):
    def __init__(
        self,
        detail: str,
        *,
        provider: str,
        status_code: int = 502,
    ) -> None:
        super().__init__(
            detail=detail,
            status_code=status_code,
            error_code=f"{provider.upper()}_LLM_ERROR",
        )
        self.provider = provider
