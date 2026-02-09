"""
Product Model - Products created by suppliers

Products are owned by suppliers and can be featured in promotions.
Supports:
- Multi-location inventory tracking
- Product variants with individual pricing and attributes
- Package dimensions per variant
- Topic-based descriptions
"""

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field, field_validator, HttpUrl
from typing import Optional, List, Dict, Annotated
from datetime import datetime
from enum import Enum

from utils.datetime_utils import utc_now


# Enums
class ProductStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    OUT_OF_STOCK = "out_of_stock"
    DISCONTINUED = "discontinued"
    DELETED = "deleted"


class ProductCategory(str, Enum):
    """Product categories matching supplier industry categories"""
    ELECTRONICS = "electronics"
    FASHION = "fashion"
    BEAUTY = "beauty"
    HOME_GARDEN = "home_garden"
    SPORTS_OUTDOORS = "sports_outdoors"
    FOOD_BEVERAGE = "food_beverage"
    HEALTH_WELLNESS = "health_wellness"
    TOYS_GAMES = "toys_games"
    BOOKS_MEDIA = "books_media"
    AUTOMOTIVE = "automotive"
    OTHER = "other"



class UnitType(str, Enum):
    """Unit of measurement for the product"""
    PIECE = "piece"
    PAIR = "pair"
    SET = "set"
    BOX = "box"
    PACK = "pack"
    BUNDLE = "bundle"
    KG = "kg"
    GRAM = "gram"
    LITER = "liter"
    ML = "ml"
    METER = "meter"
    OTHER = "other"


# Embedded Schemas
class StockLocation(BaseModel):
    """Physical location where product inventory is stored"""

    location_name: Annotated[str, Field(min_length=1, max_length=200, description="Warehouse/store name")]

    # Address
    street_address: Annotated[Optional[str], Field(None, max_length=200, description="Street address")]
    city: Annotated[str, Field(min_length=1, max_length=100, description="City")]
    state: Annotated[Optional[str], Field(None, max_length=100, description="State/Province")]
    zip_code: Annotated[str, Field(min_length=1, max_length=20, description="Postal code")]
    country: Annotated[str, Field(min_length=2, max_length=2, description="ISO country code")]

    # Inventory at this location
    quantity: Annotated[int, Field(default=0, ge=0, description="Available quantity at location")]

    @field_validator("country")
    @classmethod
    def validate_country_code(cls, v: str) -> str:
        """Ensure country code is uppercase"""
        return v.upper()

class PackageDimensions(BaseModel):
    """Package dimensions for shipping calculations"""

    width_cm: Annotated[float, Field(gt=0, description="Package width in cm")]
    height_cm: Annotated[float, Field(gt=0, description="Package height in cm")]
    depth_cm: Annotated[float, Field(gt=0, description="Package depth in cm")]



class VariantAttribute(BaseModel):
    """Product variant attribute (e.g., color, size, material)"""

    attribute_name: Annotated[str, Field(min_length=1, max_length=50, description="Attribute name (e.g., 'Color', 'Size')")]
    attribute_value: Annotated[str, Field(min_length=1, max_length=100, description="Attribute value (e.g., 'Red', 'Large')")]


class ProductVariant(BaseModel):
    """Product variant with unique attributes, pricing, and inventory"""

    variant_id: Annotated[str, Field(description="Unique variant identifier")]
    variant_name: Annotated[str, Field(min_length=1, max_length=200, description="Variant display name")]

    # Variant attributes (e.g., color: red, size: large)
    attributes: Annotated[List[VariantAttribute], Field(default_factory=list, description="Variant attributes")]


    # Pricing for this variant
    price_cents: Annotated[int, Field(ge=0, description="Variant price in cents")]
    cost_cents: Annotated[Optional[int], Field(None, ge=0, description="Variant cost in cents")]

    # Inventory for this variant (total across all locations)
    quantity: Annotated[int, Field(default=0, ge=0, description="Total quantity")]

    # Package dimensions specific to this variant
    package_dimensions: Annotated[PackageDimensions, Field(description="Shipping dimensions")]

    # Variant-specific image
    image_url: Annotated[Optional[HttpUrl], Field(None, description="Variant-specific image")]



class TopicDescription(BaseModel):
    """Topic-based product description (e.g., Features, Specifications, Care Instructions)"""

    topic: Annotated[str, Field(min_length=1, max_length=100, description="Topic name")]
    description: Annotated[str, Field(min_length=1, max_length=5000, description="Topic description")]
    display_order: Annotated[int, Field(default=0, description="Display order for topics")]


class ProductMetadata(BaseModel):
    """Product metadata and categorization"""

    # Primary identifiers
    base_sku: Annotated[str, Field(min_length=1, max_length=100, description="Base SKU (product-level, not variant)")]

    # Brand/manufacturer
    brand: Annotated[Optional[str], Field(None, max_length=100, description="Brand name")]

   


class ProductStats(BaseModel):
    """Product statistics (denormalized for performance)"""

    view_count: Annotated[int, Field(default=0, ge=0, description="Total views")]
    favorite_count: Annotated[int, Field(default=0, ge=0, description="Times favorited")]
    purchase_count: Annotated[int, Field(default=0, ge=0, description="Total purchases")]
  
    # Ratings
    total_reviews: Annotated[int, Field(default=0, ge=0, description="Total reviews")]



# Main Product Document
class Product(Document):
    """
    Product model - created and managed by suppliers

    Supports:
    - Multi-location inventory tracking
    - Product variants with individual attributes and pricing
    - Topic-based descriptions
    - Package dimensions per variant
    """

    # Supplier relationship
    supplier_id: Annotated[PydanticObjectId, Field(description="Reference to Supplier")]

    # Supplier info (denormalized)
    supplier_info: Annotated[Dict[str, str], Field(default_factory=dict, description="Cached supplier data")]

    # Basic information
    name: Annotated[str, Field(min_length=1, max_length=200, description="Product name")]

    # Short summary
    short_description: Annotated[Optional[str], Field(None, max_length=500, description="Brief summary")]

    # Topic-based descriptions
    topic_descriptions: Annotated[List[TopicDescription], Field(
        default_factory=list,
        description="Structured descriptions by topic"
    )]

    # Categorization
    category: Annotated[ProductCategory, Field(description="Primary category")]

    # Unit type
    unit_type: Annotated[UnitType, Field(default=UnitType.PIECE, description="Unit of measurement")]

    # Metadata (SKU, brand, tags)
    metadata: Annotated[ProductMetadata, Field(description="Product metadata")]

    # Stock locations (multiple warehouses/stores)
    stock_locations: Annotated[List[StockLocation], Field(
        default_factory=list,
        description="Physical stock locations"
    )]

    # Product variants (sizes, colors, etc.) - stored as dict with variant_name as key
    variants: Annotated[Dict[str, ProductVariant], Field(
        default_factory=dict,
        description="Product variants keyed by variant name"
    )]

    # Base price (if no variants, or default price)
    base_price_cents: Annotated[int, Field(ge=0, description="Base price in cents")]
  

    # Statistics
    stats: Annotated[ProductStats, Field(default_factory=ProductStats, description="Performance stats")]

    # Status
    status: Annotated[ProductStatus, Field(default=ProductStatus.DRAFT, description="Product status")]

    # Publishing
    published_at: Annotated[Optional[datetime], Field(None, description="First published timestamp")]

    # Timestamps
    created_at: Annotated[datetime, Field(default_factory=utc_now, description="Creation timestamp")]
    updated_at: Annotated[datetime, Field(default_factory=utc_now, description="Last update timestamp")]

    class Settings:
        name = "products"

        indexes = [
            # Supplier's products
            [("supplier_id", 1)],
            [("status", 1)],
            [("created_at", -1)],
        ]

    async def save(self, *args, **kwargs):
        """Override save to update timestamps"""
        self.updated_at = utc_now()
        return await super().save(*args, **kwargs)
