"""
Order Model - Purchase orders created by users

Orders capture complete purchase information including:
- Product snapshots at purchase time
- Payment and shipping details
- Order timeline and status tracking
- Idempotency for preventing duplicate orders
"""

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Dict, Annotated
from datetime import datetime
from enum import Enum

from utils.datetime_utils import utc_now


# Enums
class OrderStatus(str, Enum):
    """Overall order status"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    FAILED = "failed"


class PaymentStatus(str, Enum):
    """Payment processing status"""
    PENDING = "pending"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class FulfillmentStatus(str, Enum):
    """Order fulfillment status"""
    PENDING = "pending"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    RETURNED = "returned"


class PaymentMethod(str, Enum):
    """Payment method types"""
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    PAYPAL = "paypal"
    APPLE_PAY = "apple_pay"
    GOOGLE_PAY = "google_pay"
    BANK_TRANSFER = "bank_transfer"
    COD = "cash_on_delivery"


# Embedded Schemas
class OrderCustomer(BaseModel):
    """Customer information (denormalized from User)"""

    user_id: Annotated[PydanticObjectId, Field(description="Reference to User document")]
    display_name: Annotated[str, Field(description="Customer display name")]
    email: Annotated[EmailStr, Field(description="Customer email for receipts")]
    phone: Annotated[Optional[str], Field(None, description="Customer phone number")]


class ProductSnapshot(BaseModel):
    """Immutable snapshot of product at time of purchase"""

    product_id: Annotated[PydanticObjectId, Field(description="Reference to Product document")]
    supplier_id: Annotated[PydanticObjectId, Field(description="Reference to Supplier document")]

    # Product details at purchase time
    product_name: Annotated[str, Field(description="Product name")]


    # Variant details (if applicable)
    variant_name: Annotated[Optional[str], Field(None, description="Variant name")]
    variant_attributes: Annotated[Dict[str, str], Field(default_factory=dict, description="Variant attributes")]

    # Visual
    image_url: Annotated[str, Field(description="Product/variant image URL")]

    # Supplier info
    supplier_name: Annotated[str, Field(description="Supplier business name")]


class OrderItem(BaseModel):
    """Individual item in the order"""

    item_id: Annotated[str, Field(description="Unique item identifier within order")]

    # Product snapshot
    product_snapshot: Annotated[ProductSnapshot, Field(description="Product details at purchase time")]

    # Quantity and pricing
    quantity: Annotated[int, Field(ge=1, description="Quantity ordered")]
    unit_price_cents: Annotated[int, Field(ge=0, description="Price per unit in cents")]

    # Discounts applied to this item
    final_price_cents: Annotated[int, Field(ge=0, description="Final price after discount")]

    # Fulfillment
    fulfillment_status: Annotated[FulfillmentStatus, Field(default=FulfillmentStatus.PENDING, description="Item fulfillment status")]
    shipped_quantity: Annotated[int, Field(default=0, ge=0, description="Quantity shipped")]

    # Tracking
    tracking_number: Annotated[Optional[str], Field(None, description="Shipping tracking number")]
    carrier: Annotated[Optional[str], Field(None, description="Shipping carrier")]
    shipped_at: Annotated[Optional[datetime], Field(None, description="Shipment timestamp")]
    delivered_at: Annotated[Optional[datetime], Field(None, description="Delivery timestamp")]
    total_cents: Annotated[int, Field(ge=0, description="Grand total")]



class ShippingAddress(BaseModel):
    """Shipping address details"""

    recipient_name: Annotated[str, Field(min_length=1, max_length=200, description="Recipient full name")]
    phone: Annotated[Optional[str], Field(None, description="Contact phone number")]
    street_address_1: Annotated[str, Field(min_length=1, max_length=200, description="Street address line 1")]
    street_address_2: Annotated[Optional[str], Field(None, max_length=200, description="Street address line 2")]
    city: Annotated[str, Field(min_length=1, max_length=100, description="City")]
    state: Annotated[str, Field(min_length=1, max_length=100, description="State/Province")]
    zip_code: Annotated[str, Field(min_length=1, max_length=20, description="Postal code")]
    country: Annotated[str, Field(min_length=2, max_length=2, description="ISO country code")]


# Main Order Document
class Order(Document):
    """
    Order model - purchase orders created by users

    Captures complete purchase information with:
    - Product snapshots (immutable)
    - Payment and shipping tracking
    - Order timeline and audit trail
    - Attribution for analytics
    """

    # Order identification
    order_number: Annotated[str, Field(description="Human-readable order number (e.g., ORD-20250203-1234)")]

    # Customer
    customer: Annotated[OrderCustomer, Field(description="Customer information")]

    # Order items
    items: Annotated[List[OrderItem], Field(description="Products purchased")]

    

    # Addresses
    shipping_address: Annotated[ShippingAddress, Field(description="Delivery address")]

    # Order status
    status: Annotated[OrderStatus, Field(default=OrderStatus.PENDING, description="Overall order status")]

    # Timestamps
    created_at: Annotated[datetime, Field(default_factory=utc_now, description="Order creation timestamp")]
    updated_at: Annotated[datetime, Field(default_factory=utc_now, description="Last update timestamp")]

    class Settings:
        name = "orders"

        indexes = [
            # Unique order number
           
            # Customer's orders
            [("customer.user_id", 1), ("created_at", -1)],

            # Order status filtering
            [("status", 1), ("created_at", -1)],


            # Orders by date range
            [("created_at", -1)],
        ]

    async def save(self, *args, **kwargs):
        """Override save to update timestamps"""
        self.updated_at = utc_now()
        return await super().save(*args, **kwargs)
