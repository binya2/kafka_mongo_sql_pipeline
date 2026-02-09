"""
Centralized Error Management - Exception hierarchy and legacy ValueError mapper.
"""

from __future__ import annotations

from enum import StrEnum
from http import HTTPStatus
from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel


# ============================================================================
# Error response schemas (OpenAPI documentation)
# ============================================================================

class ErrorDetail(BaseModel):
    """Error detail body"""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Standard error response envelope"""
    error: ErrorDetail


# ============================================================================
# Error code enum
# ============================================================================

class ErrorCode(StrEnum):
    """Static error codes used across the application."""

    INTERNAL_ERROR = "INTERNAL_ERROR"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    STATE_CONFLICT = "STATE_CONFLICT"
    FORBIDDEN = "FORBIDDEN"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    ACCOUNT_STATUS_ERROR = "ACCOUNT_STATUS_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    INSUFFICIENT_STOCK = "INSUFFICIENT_STOCK"
    DUPLICATE_RESOURCE = "DUPLICATE_RESOURCE"
    INVALID_TOKEN = "INVALID_TOKEN"


# ============================================================================
# Base exception
# ============================================================================

class AppError(Exception):
    """Base application error. All typed exceptions inherit from this."""

    status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code: str = ErrorCode.INTERNAL_ERROR

    def __init__(
        self,
        message: str,
        *,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        if error_code is not None:
            self.error_code = error_code
        self.details = details


# ============================================================================
# Concrete subclasses
# ============================================================================

class NotFoundError(AppError):
    status_code = HTTPStatus.NOT_FOUND
    error_code = ErrorCode.RESOURCE_NOT_FOUND


class ValidationError(AppError):
    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
    error_code = ErrorCode.VALIDATION_ERROR


class StateConflictError(AppError):
    status_code = HTTPStatus.CONFLICT
    error_code = ErrorCode.STATE_CONFLICT


class AuthorizationError(AppError):
    status_code = HTTPStatus.FORBIDDEN
    error_code = ErrorCode.FORBIDDEN


class AuthenticationError(AppError):
    status_code = HTTPStatus.UNAUTHORIZED
    error_code = ErrorCode.AUTHENTICATION_FAILED


class AccountStatusError(AppError):
    status_code = HTTPStatus.FORBIDDEN
    error_code = ErrorCode.ACCOUNT_STATUS_ERROR


class RateLimitError(AppError):
    status_code = HTTPStatus.TOO_MANY_REQUESTS
    error_code = ErrorCode.RATE_LIMITED


class VersionConflictError(AppError):
    status_code = HTTPStatus.CONFLICT
    error_code = ErrorCode.VERSION_CONFLICT


class InsufficientStockError(AppError):
    status_code = HTTPStatus.CONFLICT
    error_code = ErrorCode.INSUFFICIENT_STOCK


class DuplicateError(AppError):
    status_code = HTTPStatus.CONFLICT
    error_code = ErrorCode.DUPLICATE_RESOURCE


class TokenError(AppError):
    status_code = HTTPStatus.BAD_REQUEST
    error_code = ErrorCode.INVALID_TOKEN


# ============================================================================
# Legacy ValueError mapper (ordered predicate rules, first match wins)
# ============================================================================

_Rule = tuple[Callable[[str], bool], type[AppError]]


def _contains(*keywords: str) -> Callable[[str], bool]:
    """Return a predicate that matches if the message contains *any* keyword (case-insensitive)."""
    lowered = [k.lower() for k in keywords]
    return lambda msg: any(k in msg.lower() for k in lowered)


class ValueErrorMapper:
    """Maps legacy ``ValueError`` message strings to ``AppError`` subclasses.

    Rules are evaluated in order; the **first** matching predicate wins.
    Rules are ordered from most specific to least specific.
    """

    _rules: list[_Rule] = [
        # --- most specific first ---
        (_contains("version conflict", "has been modified"), VersionConflictError),
        (_contains("insufficient stock", "not enough stock", "out of stock", "insufficient inventory"), InsufficientStockError),
        (_contains("already exists", "already in use", "duplicate", "already registered", "already a member"), DuplicateError),
        (_contains("expired", "invalid token", "token not found", "invalid reset token", "invalid or expired"), TokenError),
        (_contains("too many attempts", "locked", "rate limit"), RateLimitError),
        (_contains("suspended", "pending approval", "account is pending", "not approved", "account is deleted", "account status"), AccountStatusError),
        (_contains("invalid email or password", "invalid credentials", "authentication failed"), AuthenticationError),
        (_contains("not authorized", "permission", "forbidden", "not the owner", "only the", "not a member", "must be", "cannot manage", "do not have"), AuthorizationError),
        (_contains("cannot", "status", "not in", "invalid state", "is not", "can only"), StateConflictError),
        (_contains("not found", "no ", "does not exist"), NotFoundError),
        # --- catch-all ---
    ]

    @classmethod
    def map(cls, error: ValueError) -> AppError:
        """Convert a ``ValueError`` to the best-matching ``AppError`` subclass."""
        msg = str(error)
        for predicate, exc_class in cls._rules:
            if predicate(msg):
                return exc_class(msg)
        # Fallback: treat as validation error
        return ValidationError(msg)
