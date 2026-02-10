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
        if ts is None:
            return None
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))

    def handle_order_created(self, event: dict):
        data = event.get("data", {})
        customer_id = data.get("customer_id")
        shipping_address = data.get("shipping_address", {})
        order_payload = {
            "order_id": event.get("entity_id"),
            "order_number": data.get("order_number"),
            "customer_user_id": customer_id,
            "customer_display_name": data.get("customer_display_name"),
            "customer_email": data.get("customer_email"),
            "customer_phone": data.get("customer_phone"),
            "shipping_recipient_name": shipping_address.get("recipient_name"),
            "shipping_phone": shipping_address.get("phone"),
            "shipping_street_1": shipping_address.get("street_1"),
            "shipping_street_2": shipping_address.get("street_2"),
            "shipping_city": shipping_address.get("city"),
            "shipping_state": shipping_address.get("state"),
            "shipping_zip_code": shipping_address.get("zip_code"),
            "shipping_country": shipping_address.get("country"),
            "status": data.get("status"),
            "created_at": self._parse_ts(data.get("created_at")),
            "updated_at": self._parse_ts(data.get("updated_at")),
            "event_id": event.get("event_id"),
            "event_timestamp": self._parse_ts(event.get("timestamp"))
        }
        self._dal.insert_order(**order_payload)

        item_data = data.get("items", [])
        items = []
        for item in item_data:
            snapshot = item.get('product_snapshot', {})
            temp = item | snapshot
            temp.pop('product_snapshot', None)
            items.append(temp)

        if items:
            self._dal.insert_order_items(event.get("entity_id"), items)
        logger.info(f"Order created: {event.get('event_id')}")

    def handle_order_cancelled(self, event: dict):
        data = event.get("data", {})
        self._dal.cancel_order(order_number=data.get("order_number"),
                               event_id=event.get("event_id"),
                               event_timestamp=self._parse_ts(event.get("timestamp"))
                               )
        logger.info(f"Order cancelled: {event.get('event_id')}")

    def get_handlers(self) -> dict:
        return {
            EventType.ORDER_CREATED: self.handle_order_created,
            EventType.ORDER_CANCELLED: self.handle_order_cancelled,
        }
