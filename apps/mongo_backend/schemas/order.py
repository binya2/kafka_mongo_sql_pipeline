"""
Order Schemas - Request and Response models for Order API
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict

from datetime import datetime


# ============================================================
# Request Schemas
# ============================================================

class ShippingAddressRequest(BaseModel):
    """Shipping address for order"""
    recipient_name: str = Field(..., min_length=1, max_length=200, description="Recipient full name")
    phone: Optional[str] = Field(None, max_length=20, description="Contact phone number")
    street_address_1: str = Field(..., min_length=1, max_length=200, description="Street address line 1")
    street_address_2: Optional[str] = Field(None, max_length=200, description="Street address line 2")
    city: str = Field(..., min_length=1, max_length=100, description="City")
    state: str = Field(..., min_length=1, max_length=100, description="State/Province")
    zip_code: str = Field(..., min_length=1, max_length=20, description="Postal code")
    country: str = Field(..., min_length=2, max_length=2, description="ISO 2-letter country code")
    delivery_notes: Optional[str] = Field(None, max_length=500, description="Special delivery instructions")


class BillingAddressRequest(BaseModel):
    """Billing address for order"""
    billing_name: str = Field(..., min_length=1, max_length=200, description="Name on payment method")
    street_address_1: str = Field(..., min_length=1, max_length=200, description="Street address line 1")
    street_address_2: Optional[str] = Field(None, max_length=200, description="Street address line 2")
    city: str = Field(..., min_length=1, max_length=100, description="City")
    state: str = Field(..., min_length=1, max_length=100, description="State/Province")
    zip_code: str = Field(..., min_length=1, max_length=20, description="Postal code")
    country: str = Field(..., min_length=2, max_length=2, description="ISO 2-letter country code")


class OrderItemRequest(BaseModel):
    """Item to add to order"""
    product_id: str = Field(..., description="Product ID")
    variant_name: Optional[str] = Field(None, description="Variant name if applicable")
    quantity: int = Field(..., ge=1, le=99, description="Quantity to order")


class PaymentInfoRequest(BaseModel):
    """Payment information for order"""
    payment_method: str = Field(..., description="Payment method type (credit_card, debit_card, paypal, etc.)")
    payment_provider: str = Field(default="stripe", description="Payment provider")
    card_last4: Optional[str] = Field(None, max_length=4, description="Last 4 digits of card")
    card_brand: Optional[str] = Field(None, description="Card brand (Visa, Mastercard, etc.)")


class AttributionRequest(BaseModel):
    """Order attribution for marketing tracking"""
    promotion_id: Optional[str] = Field(None, description="Promotion ID if ordering through a promotion")
    community_id: Optional[str] = Field(None, description="Community ID if ordering through a community")
    referral_code: Optional[str] = Field(None, description="Referral code")
    utm_source: Optional[str] = Field(None, description="UTM source")
    utm_medium: Optional[str] = Field(None, description="UTM medium")
    utm_campaign: Optional[str] = Field(None, description="UTM campaign")


class CreateOrderRequest(BaseModel):
    """Create order request"""
    items: List[OrderItemRequest] = Field(..., min_length=1, max_length=20, description="Items to order")
    shipping_address: ShippingAddressRequest = Field(..., description="Shipping address")
    billing_address: Optional[BillingAddressRequest] = Field(None, description="Billing address (if different)")
    payment_info: PaymentInfoRequest = Field(..., description="Payment information")
    attribution: Optional[AttributionRequest] = Field(None, description="Marketing attribution")


class GetOrderRequest(BaseModel):
    """Get order by ID request"""
    order_id: str = Field(..., description="Order ID")


class GetOrderByNumberRequest(BaseModel):
    """Get order by order number request"""
    order_number: str = Field(..., description="Order number (e.g., ORD-20241215-ABC1)")


class CompleteOrderRequest(BaseModel):
    """Complete order request"""
    order_id: str = Field(..., description="Order ID")


class UpdateOrderRequest(BaseModel):
    """Update pending order request (partial update)"""
    order_id: str = Field(..., description="Order ID")
    items: Optional[List[OrderItemRequest]] = Field(None, description="Updated items")
    shipping_address: Optional[ShippingAddressRequest] = Field(None, description="Updated shipping address")
    billing_address: Optional[BillingAddressRequest] = Field(None, description="Updated billing address")


class CancelOrderRequest(BaseModel):
    """Cancel order request"""
    order_id: str = Field(..., description="Order ID")
    reason: str = Field(..., min_length=5, max_length=500, description="Cancellation reason")


# ============================================================
# Response Schemas
# ============================================================

class ProductSnapshotResponse(BaseModel):
    """Product snapshot in order item response"""
    product_id: str
    supplier_id: str
    product_name: str
    product_slug: str
    sku: str
    variant_name: Optional[str]
    variant_attributes: Dict[str, str]
    image_url: str
    supplier_name: str


class OrderItemResponse(BaseModel):
    """Order item in response"""
    item_id: str
    product_snapshot: ProductSnapshotResponse
    quantity: int
    unit_price_cents: int
    subtotal_cents: int
    discount_cents: int
    final_price_cents: int
    fulfillment_status: str
    tracking_number: Optional[str]
    carrier: Optional[str]
    shipped_at: Optional[datetime]
    delivered_at: Optional[datetime]


class OrderTotalsResponse(BaseModel):
    """Order totals in response"""
    subtotal_cents: int
    discount_cents: int
    tax_cents: int
    shipping_cents: int
    total_cents: int
    currency: str


class ShippingAddressResponse(BaseModel):
    """Shipping address in response"""
    recipient_name: str
    phone: Optional[str]
    street_address_1: str
    street_address_2: Optional[str]
    city: str
    state: str
    zip_code: str
    country: str
    delivery_notes: Optional[str]


class BillingAddressResponse(BaseModel):
    """Billing address in response"""
    billing_name: str
    street_address_1: str
    street_address_2: Optional[str]
    city: str
    state: str
    zip_code: str
    country: str


class PaymentInfoResponse(BaseModel):
    """Payment info in response"""
    payment_method: str
    payment_provider: str
    status: str
    card_last4: Optional[str]
    card_brand: Optional[str]
    transaction_id: Optional[str]
    authorized_at: Optional[datetime]
    captured_at: Optional[datetime]


class TimelineEventResponse(BaseModel):
    """Timeline event in response"""
    status: str
    timestamp: datetime
    note: Optional[str]


class OrderAttributionResponse(BaseModel):
    """Order attribution in response"""
    promotion_id: Optional[str]
    promotion_title: Optional[str]
    community_id: Optional[str]
    community_name: Optional[str]
    referral_code: Optional[str]
    utm_source: Optional[str]
    utm_medium: Optional[str]
    utm_campaign: Optional[str]


class OrderResponse(BaseModel):
    """Full order response"""
    id: str
    order_number: str
    status: str
    items: List[OrderItemResponse]
    totals: OrderTotalsResponse
    shipping_address: ShippingAddressResponse
    billing_address: Optional[BillingAddressResponse]
    payment: PaymentInfoResponse
    attribution: Optional[OrderAttributionResponse]
    timeline: List[TimelineEventResponse]
    estimated_delivery_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class OrderListItemResponse(BaseModel):
    """Order list item (summary) response"""
    id: str
    order_number: str
    status: str
    payment_status: str
    item_count: int
    total_cents: int
    currency: str
    primary_image: Optional[str]
    created_at: datetime


class PaginationResponse(BaseModel):
    """Pagination info"""
    next_cursor: Optional[str]
    has_more: bool
    page_size: int


class OrderListResponse(BaseModel):
    """Paginated order list response"""
    orders: List[OrderListItemResponse]
    pagination: PaginationResponse


class MessageResponse(BaseModel):
    """Simple message response"""
    message: str
