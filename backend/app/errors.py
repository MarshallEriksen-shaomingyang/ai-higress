from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """
    Standard error payload used by new provider/routing endpoints.

    Shape is aligned with specs/001-model-routing/contracts/* Error schema:
    {
        "error": "not_found",
        "message": "Provider not found",
        "code": 404,
        "details": {...}
    }
    """

    error: str = Field(..., description="Machine-readable error type")
    message: str = Field(..., description="Human-readable error message")
    code: int = Field(..., description="HTTP status code for this error")
    details: dict[str, Any] | None = Field(
        default=None, description="Optional structured error details"
    )


def http_error(
    status_code: int,
    *,
    error: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> HTTPException:
    """
    Helper to create an HTTPException with a standardised error body.
    """
    payload = ErrorResponse(
        error=error,
        message=message,
        code=status_code,
        details=details,
    )
    return HTTPException(status_code=status_code, detail=payload.model_dump())


def bad_request(message: str, *, details: dict[str, Any] | None = None) -> HTTPException:
    return http_error(
        status.HTTP_400_BAD_REQUEST, error="bad_request", message=message, details=details
    )


def not_found(message: str, *, details: dict[str, Any] | None = None) -> HTTPException:
    return http_error(
        status.HTTP_404_NOT_FOUND, error="not_found", message=message, details=details
    )


def forbidden(message: str, *, details: dict[str, Any] | None = None) -> HTTPException:
    return http_error(
        status.HTTP_403_FORBIDDEN,
        error="forbidden",
        message=message,
        details=details,
    )


def service_unavailable(
    message: str, *, details: dict[str, Any] | None = None
) -> HTTPException:
    return http_error(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        error="service_unavailable",
        message=message,
        details=details,
    )


__all__ = [
    "ErrorResponse",
    "bad_request",
    "forbidden",
    "http_error",
    "not_found",
    "service_unavailable",
]
