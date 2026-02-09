# Error Handling System

Single source of truth: `shared/errors.py`

## File Layout

```
shared/errors.py
├── ErrorDetail          # Pydantic model — error body
├── ErrorResponse        # Pydantic model — response envelope (OpenAPI docs)
├── ErrorCode(StrEnum)   # Static error code strings
├── AppError(Exception)  # Base exception (status_code + error_code)
├── 11 subclasses        # Typed exceptions (NotFoundError, etc.)
└── ValueErrorMapper     # Legacy ValueError → AppError converter
```

## Response Format

Every error response follows this shape:

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Product not found",
    "details": {}
  }
}
```

`details` is omitted when `None`.

## Exception Classes

| Class                  | HTTP Status | ErrorCode              | When to use                              |
|------------------------|-------------|------------------------|------------------------------------------|
| `AppError`             | 500         | `INTERNAL_ERROR`       | Base class — don't raise directly        |
| `NotFoundError`        | 404         | `RESOURCE_NOT_FOUND`   | Entity lookup fails                      |
| `ValidationError`      | 422         | `VALIDATION_ERROR`     | Business rule validation fails           |
| `StateConflictError`   | 409         | `STATE_CONFLICT`       | Invalid status transition                |
| `AuthorizationError`   | 403         | `FORBIDDEN`            | User lacks permission                    |
| `AuthenticationError`  | 401         | `AUTHENTICATION_FAILED`| Bad credentials                          |
| `AccountStatusError`   | 403         | `ACCOUNT_STATUS_ERROR` | Account suspended/pending/deleted        |
| `RateLimitError`       | 429         | `RATE_LIMITED`         | Too many attempts (login, etc.)          |
| `VersionConflictError` | 409         | `VERSION_CONFLICT`     | Optimistic locking mismatch              |
| `InsufficientStockError`| 409        | `INSUFFICIENT_STOCK`   | Not enough inventory                     |
| `DuplicateError`       | 409         | `DUPLICATE_RESOURCE`   | Unique constraint violation              |
| `TokenError`           | 400         | `INVALID_TOKEN`        | Expired/invalid reset or auth token      |

## Global Exception Handlers (server.py)

Three handlers registered on the FastAPI app, in priority order:

1. **`AppError` handler** — catches all typed exceptions, returns their `status_code`, `error_code`, and `message`.
2. **`ValueError` handler** — catches legacy `ValueError` raises, runs `ValueErrorMapper.map()` to convert to the best-matching `AppError` subclass, then returns that.
3. **`Exception` handler** — catch-all for unexpected errors, returns `500 INTERNAL_ERROR` with a generic message. Never leaks internals.

Routes do NOT need try/except — exceptions propagate to the global handlers automatically.

### Exception: forgot_password endpoints

`auth.py` and `supplier_auth.py` forgot-password routes wrap the call in `try/except Exception: pass` to **swallow all errors** and always return `200`. This prevents email enumeration.

## How to Raise Errors in Services

```python
from shared.errors import NotFoundError, ValidationError, StateConflictError

# Simple
raise NotFoundError("Product not found")

# With details dict
raise ValidationError("Invalid schedule", details={"field": "end_date", "reason": "must be in the future"})
```

Never raise bare `ValueError` in new code — use the typed exceptions.

## How to Use in Routes (OpenAPI docs)

```python
from shared.errors import ErrorResponse

@router.post(
    "/example",
    response_model=SomeResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Not found"},
        409: {"model": ErrorResponse, "description": "Conflict"},
    }
)
```

The `responses` dict is purely for OpenAPI documentation. The actual error formatting is handled by the global handlers.

## Adding a New Error Type

1. Add a member to `ErrorCode(StrEnum)` in `shared/errors.py`.
2. Create a subclass of `AppError` with the appropriate `HTTPStatus` and `ErrorCode`.
3. If the error can come from legacy `ValueError` messages, add a rule to `ValueErrorMapper._rules` (ordered most-specific first).
4. Update this table above.

## ValueErrorMapper

Backward-compatibility layer for services that still raise `ValueError`. Rules are ordered most-specific first — first match wins. The catch-all fallback maps unmatched `ValueError` to `ValidationError` (422).

This mapper should shrink over time as services migrate to typed exceptions. Do not add new `ValueError` raises — use typed exceptions instead.

## Import Pattern

All imports come from `shared.errors`:

```python
# Services — import exception classes
from shared.errors import NotFoundError, ValidationError, StateConflictError

# Routes — import the OpenAPI response model
from shared.errors import ErrorResponse

# server.py — import handler dependencies
from shared.errors import AppError, ValueErrorMapper, ErrorCode
```
