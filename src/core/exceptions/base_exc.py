"""Base application exception."""

from __future__ import annotations


class AppException(Exception):
    """Base exception for all application-level errors."""

    def __init__(
        self,
        detail: str,
        status_code: int = 400,
        error_code: str = "APP_ERROR",
    ) -> None:
        self.detail = detail
        self.status_code = status_code
        self.error_code = error_code

        super().__init__(detail)
