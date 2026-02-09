"""Product Service - Business logic and DB operations."""

from typing import Optional

from beanie import PydanticObjectId

from shared.models.product import (
    Product, ProductStatus, ProductCategory, UnitType,
    ProductMetadata, TopicDescription, StockLocation,
    ProductVariant, VariantAttribute, PackageDimensions,
)
from shared.models.supplier import Supplier
from shared.errors import NotFoundError, ValidationError
from utils.datetime_utils import utc_now
from kafka.producer import get_kafka_producer
from shared.kafka.topics import EventType
from utils.serialization import oid_to_str


class ProductService:
    """Handles product DB operations."""

    def __init__(self):
        self._kafka = get_kafka_producer()

    # ----------------------------------------------------------------
    # Helpers for building embedded documents from request data
    # ----------------------------------------------------------------

    @staticmethod
    def _build_topic_descriptions(items: list) -> list[TopicDescription]:
        # TODO: Implement _build_topic_descriptions
        # Convert a list of request objects into TopicDescription embedded documents
        # Each item has: topic, description, display_order
        pass

    @staticmethod
    def _build_stock_locations(items: list) -> list[StockLocation]:
        # TODO: Implement _build_stock_locations
        # Convert a list of request objects into StockLocation embedded documents
        # Each item has: location_name, street_address, city, state, zip_code, country, quantity
        pass

    @staticmethod
    def _build_variants(variants_dict: dict) -> dict[str, ProductVariant]:
        # TODO: Implement _build_variants
        # Convert a dict of request objects into ProductVariant embedded documents
        # Each variant has: variant_id, variant_name, attributes (list of VariantAttribute),
        #   price_cents, cost_cents, quantity, package_dimensions (PackageDimensions), image_url
        pass

    # ----------------------------------------------------------------
    # CRUD
    # ----------------------------------------------------------------

    async def create_product(self, supplier_id: str, body) -> Product:
        """Create a product in draft status. `body` is a CreateProductRequest."""
        # TODO: Implement create_product
        # 1. Validate supplier exists using Supplier.get()
        # 2. Build Product document with all fields from body:
        #    - supplier_id, supplier_info (from supplier's company_info)
        #    - name, short_description, topic_descriptions (use helper)
        #    - category (ProductCategory), unit_type (UnitType)
        #    - metadata (ProductMetadata with base_sku, brand)
        #    - stock_locations (use helper), variants (use helper)
        #    - base_price_cents
        # 3. Insert into MongoDB
        # 4. Append product.id to supplier.product_ids and save supplier
        # 5. Emit PRODUCT_CREATED Kafka event
        # 6. Return the created product
        pass

    async def get_product(self, product_id: str) -> Product:
        # TODO: Implement get_product
        # 1. Fetch product by ID using Product.get()
        # 2. Handle invalid ObjectId (raise NotFoundError)
        # 3. Check product exists and status is not DELETED
        # 4. Return the product
        pass

    async def list_products(
        self,
        skip: int = 0,
        limit: int = 20,
        status_filter: Optional[str] = None,
        category: Optional[str] = None,
        supplier_id: Optional[str] = None,
    ) -> list[Product]:
        # TODO: Implement list_products
        # 1. Build query: exclude DELETED products by default
        # 2. If status_filter provided, parse comma-separated statuses into $in query
        # 3. If category provided, add to query
        # 4. If supplier_id provided, add to query (convert to PydanticObjectId)
        # 5. Sort by -created_at, apply skip/limit (cap at 100)
        # 6. Return the list
        pass

    async def update_product(self, product_id: str, body) -> Product:
        """Partial update. `body` is an UpdateProductRequest."""
        # TODO: Implement update_product
        # 1. Fetch the product using get_product
        # 2. Update only the provided fields:
        #    name, short_description, category, base_price_cents,
        #    base_sku, brand, topic_descriptions, stock_locations, variants
        # 3. Save the updated document
        # 4. Emit PRODUCT_UPDATED Kafka event
        # 5. Return the updated product
        pass

    async def delete_product(self, product_id: str) -> None:
        # TODO: Implement delete_product (soft delete via status)
        # 1. Fetch the product using get_product
        # 2. Set status to ProductStatus.DELETED
        # 3. Save the document
        # 4. Remove product.id from supplier.product_ids (handle errors gracefully)
        # 5. Emit PRODUCT_DELETED Kafka event
        pass

    # ----------------------------------------------------------------
    # Lifecycle
    # ----------------------------------------------------------------

    async def publish_product(self, product_id: str) -> Product:
        # TODO: Implement publish_product
        # 1. Fetch the product using get_product
        # 2. Validate status is DRAFT (raise ValidationError otherwise)
        # 3. Set status to ACTIVE and published_at to current UTC time
        # 4. Save the document
        # 5. Emit PRODUCT_PUBLISHED Kafka event
        # 6. Return the updated product
        pass

    async def discontinue_product(self, product_id: str) -> Product:
        # TODO: Implement discontinue_product
        # 1. Fetch the product using get_product
        # 2. Validate status is ACTIVE or OUT_OF_STOCK (raise ValidationError otherwise)
        # 3. Set status to DISCONTINUED
        # 4. Save the document
        # 5. Emit PRODUCT_DISCONTINUED Kafka event
        # 6. Return the updated product
        pass

    async def mark_out_of_stock(self, product_id: str) -> Product:
        # TODO: Implement mark_out_of_stock
        # 1. Fetch the product using get_product
        # 2. Validate status is ACTIVE (raise ValidationError otherwise)
        # 3. Set status to OUT_OF_STOCK
        # 4. Save the document
        # 5. Emit PRODUCT_OUT_OF_STOCK Kafka event
        # 6. Return the updated product
        pass

    async def restore_product(self, product_id: str) -> Product:
        # TODO: Implement restore_product
        # 1. Fetch product by ID using Product.get() (include deleted ones)
        # 2. Handle not found
        # 3. Set status back to DRAFT
        # 4. Save the document
        # 5. Emit PRODUCT_RESTORED Kafka event
        # 6. Return the updated product
        pass
