"""
User Model - For consumers and celebrities/influencers (leaders)

Supports:
- Regular consumers (role=consumer)
- Celebrities/Influencers (role=leader) with business information
- Multiple contact emails
- Business location information for celebrities
"""

from beanie import Document
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Annotated
from datetime import datetime
from enum import Enum

from utils.datetime_utils import utc_now





# Embedded Schemas
class ContactInfo(BaseModel):
    """Contact information with primary and additional emails"""

    primary_email: Annotated[EmailStr, Field(description="Primary email for login")]
    additional_emails: Annotated[List[EmailStr], Field(default_factory=list, description="Additional contact emails")]
    phone: Annotated[Optional[str], Field(None, description="Phone with country code")]


class BusinessAddress(BaseModel):
    """Business address for celebrity/leader accounts"""

    street: Annotated[Optional[str], Field(None, max_length=200, description="Street address")]
    city: Annotated[str, Field(min_length=1, max_length=100, description="City")]
    state: Annotated[str, Field(min_length=1, max_length=100, description="State/Province")]
    zip_code: Annotated[str, Field(min_length=1, max_length=20, description="Postal/ZIP code")]
    country: Annotated[str, Field(min_length=2, max_length=2, description="ISO 3166-1 alpha-2 country code")]



class UserProfile(BaseModel):
    """User profile information"""

    display_name: Annotated[str, Field(min_length=1, max_length=100, description="Public display name")]
    avatar: Annotated[str, Field(default="https://cdn.example.com/avatars/default.jpg", description="Avatar image URL")]
    bio: Annotated[Optional[str], Field(None, max_length=500, description="User biography")]
    date_of_birth: Annotated[Optional[datetime], Field(None, description="Date of birth")]

    # Celebrity/Leader business info (only if role=leader)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: str) -> str:
        """Ensure display name is not empty"""
        if not v.strip():
            raise ValueError("Display name cannot be empty")
        return v.strip()



# Main User Document
class User(Document):
    """
    User model for consumers and celebrities/influencers

    - Consumers: Regular shoppers who browse and purchase
    - Leaders (Celebrities): Can manage communities and have business info
    """

    # Authentication
    password_hash: Annotated[str, Field(description="Bcrypt hashed password")]

    # Contact information
    contact_info: Annotated[ContactInfo, Field(description="Contact details")]

    # Role

    # Profile
    profile: Annotated[UserProfile, Field(description="User profile data")]


    # Soft delete
    deleted_at: Annotated[Optional[datetime], Field(None, description="Soft delete timestamp")]

    # Optimistic locking
    version: Annotated[int, Field(default=1, ge=1, description="Document version for optimistic locking")]

    # Timestamps
    created_at: Annotated[datetime, Field(default_factory=utc_now, description="Account creation timestamp")]
    updated_at: Annotated[datetime, Field(default_factory=utc_now, description="Last update timestamp")]


    async def save(self, *args, **kwargs):
        """Override save to update timestamps"""
        self.updated_at = utc_now()
        return await super().save(*args, **kwargs)
