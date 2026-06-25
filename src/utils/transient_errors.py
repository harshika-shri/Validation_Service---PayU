from __future__ import annotations

import socket
import urllib.error

from src.core.exceptions.base_exc import AppException
from src.core.exceptions.llm_exc import LLMServiceError

TRANSIENT_HTTP_STATUS_CODES = {
    408,
    429,
    500,
    502,
    503,
    504,
}


def is_transient_error(
    error: BaseException,
) -> bool:
    if isinstance(
        error,
        (
            ConnectionError,
            TimeoutError,
            OSError,
            socket.timeout,
            urllib.error.URLError,
        ),
    ):
        return True

    if isinstance(
        error,
        LLMServiceError,
    ):
        return (
            error.status_code
            in TRANSIENT_HTTP_STATUS_CODES
            or error.status_code >= 500
        )

    return False


def is_permanent_business_error(
    error: BaseException,
) -> bool:
    return isinstance(
        error,
        AppException,
    ) and not isinstance(
        error,
        LLMServiceError,
    )
