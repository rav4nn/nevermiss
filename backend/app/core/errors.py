from __future__ import annotations

from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.logging import get_logger


class ErrorCode(StrEnum):
    UNAUTHENTICATED = "UNAUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    TIER_REQUIRED = "TIER_REQUIRED"
    SCAN_IN_PROGRESS = "SCAN_IN_PROGRESS"
    GMAIL_REAUTH_REQUIRED = "GMAIL_REAUTH_REQUIRED"
    LLM_ERROR = "LLM_ERROR"
    INTERNAL = "INTERNAL"


class AppError(Exception):
    """
    Application-level error. Raised in services and route handlers.
    T-009 registers the FastAPI exception handler that converts this to
    the standard {"error": {"code": ..., "message": ..., "details": ...}} response.
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details: dict[str, Any] = details or {}


def _error_payload(exc: AppError) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "error": {
            "code": exc.code.value,
            "message": exc.message,
        }
    }
    if exc.details:
        payload["error"]["details"] = exc.details
    return payload


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    logger = get_logger("app.error")
    logger.warning(
        "application_error",
        error_code=exc.code.value,
        status_code=exc.status_code,
        details=exc.details or None,
    )
    return JSONResponse(status_code=exc.status_code, content=_error_payload(exc))


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
