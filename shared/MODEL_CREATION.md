# Model Creation Guide

All Pydantic models in `shared/models/`. Every field must use `Annotated[Type, Field(...)]`.

## Field Pattern

```python
# CORRECT - always use Annotated
name: Annotated[str, Field(min_length=1, max_length=200, description="Product name")]
status: Annotated[UserStatus, Field(default=UserStatus.PENDING, description="Account status")]
bio: Annotated[Optional[str], Field(None, max_length=500, description="User biography")]
tags: Annotated[List[str], Field(default_factory=list, description="Tags")]
stats: Annotated[UserStats, Field(default_factory=UserStats, description="Statistics")]

# WRONG - never use bare Field()
name: str = Field(...)
status: UserStatus = Field(default=UserStatus.PENDING)
bio: Optional[str] = Field(None)
```

## Imports

```python
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Annotated
from datetime import datetime
from enum import Enum
```

## Enums

Always `(str, Enum)` for JSON serialization:

```python
class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
```

## BaseModel

```python
class ShippingAddress(BaseModel):
    """Shipping address details"""

    recipient_name: Annotated[str, Field(min_length=1, max_length=200, description="Recipient full name")]
    phone: Annotated[Optional[str], Field(None, description="Contact phone")]
    city: Annotated[str, Field(min_length=1, max_length=100, description="City")]
    country: Annotated[str, Field(min_length=2, max_length=2, description="ISO country code")]

    @field_validator("country")
    @classmethod
    def validate_country(cls, v: str) -> str:
        return v.upper()
```

## Field Defaults Cheat Sheet

| Scenario | Pattern |
|----------|---------|
| Required | `Annotated[str, Field(description="...")]` |
| Required + constraints | `Annotated[str, Field(min_length=1, max_length=200, description="...")]` |
| Optional (None) | `Annotated[Optional[str], Field(None, description="...")]` |
| Default value | `Annotated[int, Field(default=0, ge=0, description="...")]` |
| Default enum | `Annotated[Status, Field(default=Status.PENDING, description="...")]` |
| Default factory (mutable) | `Annotated[List[str], Field(default_factory=list, description="...")]` |
| Default factory (model) | `Annotated[Stats, Field(default_factory=Stats, description="...")]` |
| Numeric constraints | `Annotated[int, Field(ge=0, le=100, description="...")]` |
| Regex pattern | `Annotated[str, Field(pattern="^#[0-9A-Fa-f]{6}$", description="...")]` |
| Datetime with factory | `Annotated[datetime, Field(default_factory=utc_now, description="...")]` |

## Validators

Always `@field_validator` with `@classmethod`:

```python
@field_validator("slug")
@classmethod
def validate_slug(cls, v: str) -> str:
    slug = v.lower().strip()
    if not all(c.isalnum() or c in '-_' for c in slug):
        raise ValueError("Slug can only contain letters, numbers, hyphens, underscores")
    return slug

@field_validator("tags")
@classmethod
def validate_tags(cls, v: List[str]) -> List[str]:
    if not v:
        return v
    return list(set(tag.lower().strip() for tag in v if tag.strip()))
```

Cross-field validation (access other fields via `info.data`):

```python
@field_validator("profile")
@classmethod
def validate_leader_business_info(cls, v: UserProfile, info) -> UserProfile:
    role = info.data.get("role")
    if role == UserRole.LEADER and not v.celebrity_business_info:
        raise ValueError("Leaders must have celebrity_business_info")
    return v
```

## File Structure

Each file contains: enums first, then embedded BaseModel schemas, then the main model.

```
shared/models/
├── __init__.py
├── user.py
├── community.py
├── product.py
├── order.py
├── promotion.py
├── post.py
├── post_change_request.py
└── supplier.py
```
