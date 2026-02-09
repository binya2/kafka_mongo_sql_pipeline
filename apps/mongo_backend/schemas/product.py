"""
Product Request/Response Schemas
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict

from datetime import datetime


# Request Schemas
class ProductImageRequest(BaseModel):
    """Product image"""
    url: HttpUrl = Field(..., description="Image URL")
    alt_text: Optional[str] = Field(None, max_length=200, description="Alt text for image")
    order: int = Field(default=0, ge=0, description="Display order")
    is_primary: bool = Field(default=False, description="Is primary image")


class VariantAttributeRequest(BaseModel):
    """Variant attribute"""
    attribute_name: str = Field(..., min_length=1, max_length=50)
    attribute_value: str = Field(..., min_length=1, max_length=100)


class PackageDimensionsRequest(BaseModel):
    """Package dimensions"""
    width_cm: float = Field(..., gt=0)
    height_cm: float = Field(..., gt=0)
    depth_cm: float = Field(..., gt=0)
    weight_grams: int = Field(..., gt=0)


class ProductVariantRequest(BaseModel):
    """Product variant"""
    variant_id: str = Field(..., min_length=1, max_length=50)
    variant_name: str = Field(..., min_length=1, max_length=200)
    attributes: List[VariantAttributeRequest] = Field(default_factory=list)
    sku: str = Field(..., min_length=1, max_length=100)
    price_cents: int = Field(..., ge=0)
    cost_cents: Optional[int] = Field(None, ge=0)
    quantity: int = Field(default=0, ge=0)
    package_dimensions: PackageDimensionsRequest = Field(...)
    image_url: Optional[HttpUrl] = Field(None)


class StockLocationRequest(BaseModel):
    """Stock location"""
    location_id: str = Field(..., min_length=1, max_length=50)
    location_name: str = Field(..., min_length=1, max_length=200)
    street_address: Optional[str] = Field(None, max_length=200)
    city: str = Field(..., min_length=1, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    zip_code: str = Field(..., min_length=1, max_length=20)
    country: str = Field(..., min_length=2, max_length=2)
    quantity: int = Field(default=0, ge=0)
    reserved: int = Field(default=0, ge=0)


class TopicDescriptionRequest(BaseModel):
    """Topic description"""
    topic: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=5000)
    display_order: int = Field(default=0)


class ShippingInfoRequest(BaseModel):
    """Shipping info"""
    free_shipping: bool = Field(default=False)
    shipping_cost_cents: Optional[int] = Field(None, ge=0)
    ships_from_country: str = Field(..., min_length=2, max_length=2)
    ships_to_countries: List[str] = Field(default_factory=list)
    estimated_delivery_days: Optional[int] = Field(None, ge=1)


class CreateProductRequest(BaseModel):
    """Create product request"""
    name: str = Field(..., min_length=1, max_length=200, description="Product name (must be globally unique)")
    short_description: Optional[str] = Field(None, max_length=500)
    topic_descriptions: List[TopicDescriptionRequest] = Field(default_factory=list)
    category: str = Field(..., description="Product category")
    condition: str = Field(default="new")
    unit_type: str = Field(default="piece")
    images: List[ProductImageRequest] = Field(..., min_items=1, description="At least one image required")
    base_sku: str = Field(..., min_length=1, max_length=100, description="Base SKU")
    barcode: Optional[str] = Field(None, max_length=50)
    brand: Optional[str] = Field(None, max_length=100)
    manufacturer: Optional[str] = Field(None, max_length=100)
    model_number: Optional[str] = Field(None, max_length=100)
    tags: List[str] = Field(default_factory=list)
    variants: Dict[str, ProductVariantRequest] = Field(default_factory=dict)
    stock_locations: List[StockLocationRequest] = Field(default_factory=list)
    base_price_cents: int = Field(..., ge=0, description="Base price in cents")
    currency: str = Field(default="USD", min_length=3, max_length=3)
    shipping: ShippingInfoRequest = Field(...)
    custom_attributes: Dict[str, str] = Field(default_factory=dict)


class UpdateProductRequest(BaseModel):
    """Update product request (partial update)"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    short_description: Optional[str] = Field(None, max_length=500)
    topic_descriptions: Optional[List[TopicDescriptionRequest]] = None
    category: Optional[str] = None
    condition: Optional[str] = None
    images: Optional[List[ProductImageRequest]] = None
    base_sku: Optional[str] = Field(None, min_length=1, max_length=100)
    brand: Optional[str] = Field(None, max_length=100)
    tags: Optional[List[str]] = None
    variants: Optional[Dict[str, ProductVariantRequest]] = None
    stock_locations: Optional[List[StockLocationRequest]] = None
    base_price_cents: Optional[int] = Field(None, ge=0)
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    shipping: Optional[ShippingInfoRequest] = None
    custom_attributes: Optional[Dict[str, str]] = None


# Response Schemas
class ProductImageResponse(BaseModel):
    """Product image response"""
    url: str
    alt_text: Optional[str]
    order: int
    is_primary: bool


class ProductVariantResponse(BaseModel):
    """Product variant response"""
    variant_id: str
    variant_name: str
    sku: str
    price_cents: int
    quantity: int
    available: int
    is_active: bool


class ProductListItemResponse(BaseModel):
    """Product list item (summary)"""
    id: str
    name: str
    slug: str
    status: str
    category: str
    base_price_cents: int
    currency: str
    primary_image: Optional[str]
    stock_quantity: int
    is_available: bool
    created_at: datetime
    updated_at: datetime


class SupplierInfoResponse(BaseModel):
    """Supplier info in product response"""
    id: str
    name: str
    logo: Optional[str]


class ProductResponse(BaseModel):
    """Full product response"""
    id: str
    supplier_id: str
    supplier_info: Optional[SupplierInfoResponse]
    name: str
    slug: str
    short_description: Optional[str]
    category: str
    condition: str
    status: str
    is_available: bool
    base_price_cents: int
    currency: str
    images: List[ProductImageResponse]
    tags: List[str]
    stock_quantity: int
    variant_count: int
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime]
    deleted_at: Optional[datetime]


class PaginationResponse(BaseModel):
    """Pagination metadata"""
    next_cursor: Optional[str]
    has_more: bool
    page_size: int
    total_count: Optional[int] = None


class ProductListResponse(BaseModel):
    """Product list response"""
    products: List[ProductListItemResponse]
    pagination: PaginationResponse


class MessageResponse(BaseModel):
    """Generic message response"""
    message: str


