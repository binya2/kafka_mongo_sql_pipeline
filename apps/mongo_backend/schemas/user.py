"""
User & Supplier Request Schemas
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List


# ----------------------------------------------------------------
# User Requests
# ----------------------------------------------------------------

class CreateUserRequest(BaseModel):
    """Create a new user"""
    email: EmailStr = Field(..., description="Primary email")
    password: str = Field(..., min_length=8, max_length=128, description="Password")
    display_name: str = Field(..., min_length=1, max_length=100, description="Display name")
    phone: Optional[str] = Field(None, max_length=20, description="Phone number")
    bio: Optional[str] = Field(None, max_length=500, description="User bio")


class UpdateUserRequest(BaseModel):
    """Update user profile (partial)"""
    display_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    bio: Optional[str] = Field(None, max_length=500)
    avatar: Optional[str] = Field(None, description="Avatar URL")


# ----------------------------------------------------------------
# Supplier Requests
# ----------------------------------------------------------------

class ContactInfoRequest(BaseModel):
    primary_email: EmailStr
    additional_emails: List[EmailStr] = Field(default_factory=list)
    primary_phone: str
    contact_person_name: Optional[str] = None
    contact_person_title: Optional[str] = None
    contact_person_email: Optional[EmailStr] = None
    contact_person_phone: Optional[str] = None


class CompanyAddressRequest(BaseModel):
    street_address_1: str = Field(..., min_length=1, max_length=200)
    street_address_2: Optional[str] = Field(None, max_length=200)
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=1, max_length=100)
    zip_code: str = Field(..., min_length=1, max_length=20)
    country: str = Field(..., min_length=2, max_length=2)


class CompanyInfoRequest(BaseModel):
    legal_name: str = Field(..., min_length=2, max_length=200)
    dba_name: Optional[str] = Field(None, max_length=200)
    business_address: CompanyAddressRequest
    shipping_address: Optional[CompanyAddressRequest] = None


class BusinessInfoRequest(BaseModel):
    facebook_url: Optional[str] = None
    instagram_handle: Optional[str] = None
    twitter_handle: Optional[str] = None
    linkedin_url: Optional[str] = None
    timezone: Optional[str] = None
    support_email: Optional[EmailStr] = None
    support_phone: Optional[str] = None


class BankingInfoRequest(BaseModel):
    bank_name: Optional[str] = None
    account_holder_name: Optional[str] = None
    account_number_last4: Optional[str] = None


class CreateSupplierRequest(BaseModel):
    """Create a new supplier"""
    password: str = Field(..., min_length=8, max_length=128)
    contact_info: ContactInfoRequest
    company_info: CompanyInfoRequest
    business_info: BusinessInfoRequest = Field(default_factory=BusinessInfoRequest)
    banking_info: Optional[BankingInfoRequest] = None


class UpdateSupplierRequest(BaseModel):
    """Update supplier (partial)"""
    primary_phone: Optional[str] = Field(None)
    legal_name: Optional[str] = Field(None, min_length=2, max_length=200)
    dba_name: Optional[str] = Field(None, max_length=200)
    support_email: Optional[str] = Field(None)
    support_phone: Optional[str] = Field(None)
