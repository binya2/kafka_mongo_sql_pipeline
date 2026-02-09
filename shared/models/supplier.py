"""
Supplier Model - For business entities that supply products

Suppliers are separate from users and have:
- Company information
- Business contact details
- Verification workflow
- Product/promotion management capabilities
"""

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Annotated
from datetime import datetime
from enum import Enum

from utils.datetime_utils import utc_now




# Embedded Schemas
class SupplierContactInfo(BaseModel):
    """Contact information for supplier"""

    primary_email: Annotated[EmailStr, Field(description="Primary business email for login")]
    additional_emails: Annotated[List[EmailStr], Field(default_factory=list, description="Additional contact emails")]
    primary_phone: Annotated[str, Field(description="Primary business phone")]

    # Contact person
    contact_person_name: Annotated[Optional[str], Field(None, description="Primary contact person name")]
    contact_person_title: Annotated[Optional[str], Field(None, description="Contact person job title")]
    contact_person_email: Annotated[Optional[EmailStr], Field(None, description="Contact person email")]
    contact_person_phone: Annotated[Optional[str], Field(None, description="Contact person direct phone")]


class CompanyAddress(BaseModel):
    """Company physical address"""

    street_address_1: Annotated[str, Field(min_length=1, max_length=200, description="Street address line 1")]
    street_address_2: Annotated[Optional[str], Field(None, max_length=200, description="Street address line 2")]
    city: Annotated[str, Field(min_length=1, max_length=100, description="City")]
    state: Annotated[str, Field(min_length=1, max_length=100, description="State/Province")]
    zip_code: Annotated[str, Field(min_length=1, max_length=20, description="Postal/ZIP code")]
    country: Annotated[str, Field(min_length=2, max_length=2, description="ISO 3166-1 alpha-2 country code")]

  
  

class CompanyInfo(BaseModel):
    """Legal company information"""

    legal_name: Annotated[str, Field(min_length=2, max_length=200, description="Legal company name")]
    dba_name: Annotated[Optional[str], Field(None, max_length=200, description="Doing Business As (DBA) name")]


    # Address
    business_address: Annotated[CompanyAddress, Field(description="Primary business address")]
    shipping_address: Annotated[Optional[CompanyAddress], Field(None, description="Shipping/warehouse address")]


class BusinessInfo(BaseModel):
    """Business operational information"""

  
    # Social media
    facebook_url: Annotated[Optional[str], Field(None, description="Facebook page URL")]
    instagram_handle: Annotated[Optional[str], Field(None, description="Instagram username")]
    twitter_handle: Annotated[Optional[str], Field(None, description="Twitter/X username")]
    linkedin_url: Annotated[Optional[str], Field(None, description="LinkedIn company page URL")]

    # Business hours
    timezone: Annotated[Optional[str], Field(None, description="Business timezone (IANA format)")]

    # Support
    support_email: Annotated[Optional[EmailStr], Field(None, description="Customer support email")]
    support_phone: Annotated[Optional[str], Field(None, description="Customer support phone")]


class BankingInfo(BaseModel):
    """Banking and payment information (encrypted at rest)"""

    # Bank account details
    bank_name: Annotated[Optional[str], Field(None, description="Bank name")]
    account_holder_name: Annotated[Optional[str], Field(None, description="Account holder name")]
    account_number_last4: Annotated[Optional[str], Field(None, description="Last 4 digits of account number")]



# Main Supplier Document
class Supplier(Document):
    """
    Supplier model for business entities that provide products

    Suppliers are NOT users - they cannot:
    - Browse social feeds
    - Join communities
    - Follow users/leaders

    They CAN:
    - Create and manage products
    - Create and manage promotions
    - View analytics and reports
    """

    # Authentication
    password_hash: Annotated[str, Field(description="Bcrypt hashed password")]

    # Contact information
    contact_info: Annotated[SupplierContactInfo, Field(description="Contact details")]

    # Company information
    company_info: Annotated[CompanyInfo, Field(description="Legal company information")]

    # Business information
    business_info: Annotated[BusinessInfo, Field(description="Business operational info")]

    # Banking (encrypted)
    banking_info: Annotated[Optional[BankingInfo], Field(None, description="Banking and payout details")]

 
    # Product references (for maintaining relationship)
    product_ids: Annotated[List[PydanticObjectId], Field(default_factory=list, description="References to all products")]
    # Timestamps
    created_at: Annotated[datetime, Field(default_factory=utc_now, description="Account creation timestamp")]
    updated_at: Annotated[datetime, Field(default_factory=utc_now, description="Last update timestamp")]

    class Settings:
        name = "suppliers"

        indexes = [
            # Find suppliers by location
            [
                ("company_info.business_address.country", 1),
                ("company_info.business_address.state", 1),
                ("company_info.business_address.city", 1)
            ],
        ]


    async def save(self, *args, **kwargs):
        """Override save to update timestamps"""
        self.updated_at = utc_now()
        return await super().save(*args, **kwargs)
