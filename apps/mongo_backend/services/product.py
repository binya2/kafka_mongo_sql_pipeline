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
from shared.kafka.topics import Topic
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
        return [
            TopicDescription(topic=td.topic, description=td.description, display_order=td.display_order)
            for td in items
        ]

    @staticmethod
    def _build_stock_locations(items: list) -> list[StockLocation]:
        return [
            StockLocation(
                location_name=sl.location_name,
                street_address=sl.street_address,
                city=sl.city,
                state=sl.state,
                zip_code=sl.zip_code,
                country=sl.country,
                quantity=sl.quantity,
            )
            for sl in items
        ]

    @staticmethod
    def _build_variants(variants_dict: dict) -> dict[str, ProductVariant]:
        variants = {}
        for key, vr in variants_dict.items():
            variants[key] = ProductVariant(
                variant_id=vr.variant_id,
                variant_name=vr.variant_name,
                attributes=[
                    VariantAttribute(attribute_name=a.attribute_name, attribute_value=a.attribute_value)
                    for a in vr.attributes
                ],
                price_cents=vr.price_cents,
                cost_cents=vr.cost_cents,
                quantity=vr.quantity,
                package_dimensions=PackageDimensions(
                    width_cm=vr.package_dimensions.width_cm,
                    height_cm=vr.package_dimensions.height_cm,
                    depth_cm=vr.package_dimensions.depth_cm,
                ),
                image_url=vr.image_url,
            )
        return variants

    # ----------------------------------------------------------------
    # CRUD
    # ----------------------------------------------------------------

    async def create_product(self, supplier_id: str, body) -> Product:
        """Create a product in draft status. `body` is a CreateProductRequest."""
        try:
            supplier = await Supplier.get(PydanticObjectId(supplier_id))
        except Exception:
            raise NotFoundError("Supplier not found")
        if not supplier:
            raise NotFoundError("Supplier not found")

        product = Product(
            supplier_id=PydanticObjectId(supplier_id),
            supplier_info={"name": supplier.company_info.legal_name},
            name=body.name,
            short_description=body.short_description,
            topic_descriptions=self._build_topic_descriptions(body.topic_descriptions),
            category=ProductCategory(body.category),
            unit_type=UnitType(body.unit_type),
            metadata=ProductMetadata(base_sku=body.base_sku, brand=body.brand),
            stock_locations=self._build_stock_locations(body.stock_locations),
            variants=self._build_variants(body.variants),
            base_price_cents=body.base_price_cents,
        )
        await product.insert()

        self._kafka.emit(
            topic=Topic.PRODUCT,
            action="created",
            entity_id=oid_to_str(product.id),
            data=product.model_dump(mode="json"),
        )
        return product

    async def get_product(self, product_id: str) -> Product:
        try:
            product = await Product.get(PydanticObjectId(product_id))
        except Exception:
            raise NotFoundError("Product not found")
        if not product or product.status == ProductStatus.DELETED:
            raise NotFoundError("Product not found")
        return product

    async def list_products(
        self,
        skip: int = 0,
        limit: int = 20,
        status_filter: Optional[str] = None,
        category: Optional[str] = None,
        supplier_id: Optional[str] = None,
    ) -> list[Product]:
        query: dict = {"status": {"$ne": ProductStatus.DELETED}}

        if status_filter:
            statuses = [s.strip() for s in status_filter.split(",")]
            query["status"] = {"$in": statuses}
        if category:
            query["category"] = category
        if supplier_id:
            query["supplier_id"] = PydanticObjectId(supplier_id)

        return (
            await Product.find(query)
            .sort("-created_at")
            .skip(skip)
            .limit(min(limit, 100))
            .to_list()
        )

    async def update_product(self, product_id: str, body) -> Product:
        """Partial update. `body` is an UpdateProductRequest."""
        product = await self.get_product(product_id)

        if body.name is not None:
            product.name = body.name
        if body.short_description is not None:
            product.short_description = body.short_description
        if body.category is not None:
            product.category = ProductCategory(body.category)
        if body.base_price_cents is not None:
            product.base_price_cents = body.base_price_cents
        if body.base_sku is not None:
            product.metadata.base_sku = body.base_sku
        if body.brand is not None:
            product.metadata.brand = body.brand
        if body.topic_descriptions is not None:
            product.topic_descriptions = self._build_topic_descriptions(body.topic_descriptions)
        if body.stock_locations is not None:
            product.stock_locations = self._build_stock_locations(body.stock_locations)
        if body.variants is not None:
            product.variants = self._build_variants(body.variants)

        await product.save()
        return product

    async def delete_product(self, product_id: str) -> None:
        product = await self.get_product(product_id)
        product.status = ProductStatus.DELETED
        await product.save()

        self._kafka.emit(
            topic=Topic.PRODUCT,
            action="deleted",
            entity_id=oid_to_str(product.id),
            data={"product_id": oid_to_str(product.id)},
        )

    # ----------------------------------------------------------------
    # Lifecycle
    # ----------------------------------------------------------------

    async def publish_product(self, product_id: str) -> Product:
        product = await self.get_product(product_id)
        if product.status != ProductStatus.DRAFT:
            raise ValidationError("Only draft products can be published")

        product.status = ProductStatus.ACTIVE
        product.published_at = utc_now()
        await product.save()

        self._kafka.emit(
            topic=Topic.PRODUCT,
            action="published",
            entity_id=oid_to_str(product.id),
            data=product.model_dump(mode="json"),
        )
        return product

    async def discontinue_product(self, product_id: str) -> Product:
        product = await self.get_product(product_id)
        if product.status not in (ProductStatus.ACTIVE, ProductStatus.OUT_OF_STOCK):
            raise ValidationError("Only active or out-of-stock products can be discontinued")

        product.status = ProductStatus.DISCONTINUED
        await product.save()
        return product

    async def mark_out_of_stock(self, product_id: str) -> Product:
        product = await self.get_product(product_id)
        if product.status != ProductStatus.ACTIVE:
            raise ValidationError("Only active products can be marked out of stock")

        product.status = ProductStatus.OUT_OF_STOCK
        await product.save()
        return product

    async def restore_product(self, product_id: str) -> Product:
        try:
            product = await Product.get(PydanticObjectId(product_id))
        except Exception:
            raise NotFoundError("Product not found")
        if not product:
            raise NotFoundError("Product not found")

        product.status = ProductStatus.DRAFT
        await product.save()
        return product
