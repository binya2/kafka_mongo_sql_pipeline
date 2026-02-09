"""Product events consumer."""

import logging
from datetime import datetime

from shared.kafka.topics import EventType
from src.dal.product_dal import ProductDAL

logger = logging.getLogger(__name__)


class ProductConsumer:

    def __init__(self):
        self._dal = ProductDAL()

    def _parse_ts(self, ts):
        if not ts:
            return None
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))

    def _handle_product_upsert(self, event: dict):
        """Shared handler for created and published (both send full model)."""
        data = event.get("data", {})
        metadata = data.get("metadata", {})
        stats = data.get("stats", {})
        supplier_info = data.get("supplier_info", {})

        self._dal.upsert_product(
            product_id=event.get("entity_id"),
            supplier_id=data.get("supplier_id"),
            supplier_name=supplier_info.get("name"),
            name=data.get("name"),
            short_description=data.get("short_description"),
            category=data.get("category"),
            unit_type=data.get("unit_type"),
            base_sku=metadata.get("base_sku"),
            brand=metadata.get("brand"),
            base_price_cents=data.get("base_price_cents"),
            status=data.get("status"),
            view_count=stats.get("view_count", 0),
            favorite_count=stats.get("favorite_count", 0),
            purchase_count=stats.get("purchase_count", 0),
            total_reviews=stats.get("total_reviews", 0),
            published_at=self._parse_ts(data.get("published_at")),
            created_at=self._parse_ts(data.get("created_at")),
            updated_at=self._parse_ts(data.get("updated_at")),
            event_id=event.get("event_id"),
            event_timestamp=self._parse_ts(event.get("timestamp")),
        )

        # Replace variants
        variants_dict = data.get("variants", {})
        variants = []
        for key, v in variants_dict.items():
            dims = v.get("package_dimensions", {})
            variants.append({
                "variant_key": key,
                "variant_id": v.get("variant_id"),
                "variant_name": v.get("variant_name"),
                "attributes": v.get("attributes", []),
                "price_cents": v.get("price_cents"),
                "cost_cents": v.get("cost_cents"),
                "quantity": v.get("quantity", 0),
                "width_cm": dims.get("width_cm"),
                "height_cm": dims.get("height_cm"),
                "depth_cm": dims.get("depth_cm"),
                "image_url": v.get("image_url"),
            })

        if variants:
            self._dal.replace_variants(event.get("entity_id"), variants)

    def handle_product_created(self, event: dict):
        self._handle_product_upsert(event)
        logger.info(f"[PRODUCT_CREATED] {event['entity_id']}")

    def handle_product_published(self, event: dict):
        self._handle_product_upsert(event)
        logger.info(f"[PRODUCT_PUBLISHED] {event['entity_id']}")

    def handle_product_deleted(self, event: dict):
        data = event.get("data", {})
        self._dal.delete_product(
            product_id=data.get("product_id") or event.get("entity_id"),
        )
        logger.info(f"[PRODUCT_DELETED] {event['entity_id']}")

    def get_handlers(self) -> dict:
        return {
            EventType.PRODUCT_CREATED: self.handle_product_created,
            EventType.PRODUCT_DELETED: self.handle_product_deleted,
            EventType.PRODUCT_PUBLISHED: self.handle_product_published,
        }
