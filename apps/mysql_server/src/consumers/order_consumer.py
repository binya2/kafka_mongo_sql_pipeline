"""Order events consumer."""

import logging
from datetime import datetime

from shared.kafka.topics import EventType
from src.dal.order_dal import OrderDAL

logger = logging.getLogger(__name__)


class OrderConsumer:

    def __init__(self):
        self._dal = OrderDAL()

    def _parse_ts(self, ts):
        if not ts:
            return None
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))

    def handle_order_created(self, event: dict):
        data = event.get("data", {})
        customer = data.get("customer", {})
        shipping = data.get("shipping_address", {})

        self._dal.insert_order(
            order_id=event.get("entity_id"),
            order_number=data.get("order_number"),
            customer_user_id=customer.get("user_id"),
            customer_display_name=customer.get("display_name"),
            customer_email=customer.get("email"),
            customer_phone=customer.get("phone"),
            shipping_recipient_name=shipping.get("recipient_name"),
            shipping_phone=shipping.get("phone"),
            shipping_street_1=shipping.get("street_address_1"),
            shipping_street_2=shipping.get("street_address_2"),
            shipping_city=shipping.get("city"),
            shipping_state=shipping.get("state"),
            shipping_zip_code=shipping.get("zip_code"),
            shipping_country=shipping.get("country"),
            status=data.get("status", "pending"),
            created_at=self._parse_ts(data.get("created_at")),
            updated_at=self._parse_ts(data.get("updated_at")),
            event_id=event.get("event_id"),
            event_timestamp=self._parse_ts(event.get("timestamp")),
        )

        # Insert order items
        items_data = data.get("items", [])
        items = []
        for item in items_data:
            snapshot = item.get("product_snapshot", {})
            items.append({
                "item_id": item.get("item_id"),
                "product_id": snapshot.get("product_id"),
                "supplier_id": snapshot.get("supplier_id"),
                "product_name": snapshot.get("product_name"),
                "variant_name": snapshot.get("variant_name"),
                "variant_attributes": snapshot.get("variant_attributes", {}),
                "image_url": snapshot.get("image_url"),
                "supplier_name": snapshot.get("supplier_name"),
                "quantity": item.get("quantity"),
                "unit_price_cents": item.get("unit_price_cents"),
                "final_price_cents": item.get("final_price_cents"),
                "total_cents": item.get("total_cents"),
                "fulfillment_status": item.get("fulfillment_status", "pending"),
                "shipped_quantity": item.get("shipped_quantity", 0),
                "tracking_number": item.get("tracking_number"),
                "carrier": item.get("carrier"),
                "shipped_at": self._parse_ts(item.get("shipped_at")),
                "delivered_at": self._parse_ts(item.get("delivered_at")),
            })

        if items:
            self._dal.insert_order_items(event.get("entity_id"), items)

        logger.info(f"[ORDER_CREATED] {event['entity_id']}")

    def handle_order_cancelled(self, event: dict):
        data = event.get("data", {})
        self._dal.cancel_order(
            order_number=data.get("order_number"),
            reason=data.get("reason"),
            event_id=event.get("event_id"),
            event_timestamp=self._parse_ts(event.get("timestamp")),
        )
        logger.info(f"[ORDER_CANCELLED] {event['entity_id']}")

    def get_handlers(self) -> dict:
        return {
            EventType.ORDER_CREATED: self.handle_order_created,
            EventType.ORDER_CANCELLED: self.handle_order_cancelled,
        }
