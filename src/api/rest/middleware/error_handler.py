"""Global exception handlers for the REST API."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import cast

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.core.exceptions.base_exc import AppException


async def handle_app_exception(
    _: Request,
    exc: AppException,
) -> JSONResponse:
    """Handle custom application exceptions."""

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error_code": exc.error_code,
        },
    )


async def handle_http_exception(
    _: Request,
    exc: HTTPException,
) -> JSONResponse:
    """Handle FastAPI HTTP exceptions."""

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
        },
    )


async def handle_validation_exception(
    _: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Handle request validation errors."""

    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
        },
    )


async def handle_unexpected_exception(
    _: Request,
    exc: Exception,
) -> JSONResponse:
    """Handle uncaught exceptions."""

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
        },
    )


def add_error_handlers(app: FastAPI) -> None:
    """Register global exception handlers."""

    app.add_exception_handler(
        AppException,
        cast(
            Callable[[Request, Exception], Awaitable[JSONResponse]],
            handle_app_exception,
        ),
    )

    app.add_exception_handler(
        HTTPException,
        cast(
            Callable[[Request, Exception], Awaitable[JSONResponse]],
            handle_http_exception,
        ),
    )

    app.add_exception_handler(
        RequestValidationError,
        cast(
            Callable[[Request, Exception], Awaitable[JSONResponse]],
            handle_validation_exception,
        ),
    )

    app.add_exception_handler(
        Exception,
        cast(
            Callable[[Request, Exception], Awaitable[JSONResponse]],
            handle_unexpected_exception,
        ),
    )
