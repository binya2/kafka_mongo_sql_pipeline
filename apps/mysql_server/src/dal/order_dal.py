"""Data Access Layer for orders and order_items tables."""

import json
import logging

from src.db.connection import get_database

logger = logging.getLogger(__name__)


class OrderDAL:

    def insert_order(self, order_id, order_number,
                     customer_user_id, customer_display_name,
                     customer_email, customer_phone,
                     shipping_recipient_name, shipping_phone,
                     shipping_street_1, shipping_street_2,
                     shipping_city, shipping_state,
                     shipping_zip_code, shipping_country,
                     status, created_at, updated_at,
                     event_id, event_timestamp):
        conn = get_database().get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO orders
                    (order_id, order_number,
                     customer_user_id, customer_display_name,
                     customer_email, customer_phone,
                     shipping_recipient_name, shipping_phone,
                     shipping_street_1, shipping_street_2,
                     shipping_city, shipping_state,
                     shipping_zip_code, shipping_country,
                     status, created_at, updated_at,
                     event_id, event_timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    status=VALUES(status),
                    updated_at=VALUES(updated_at),
                    event_id=VALUES(event_id),
                    event_timestamp=VALUES(event_timestamp)
            """, (order_id, order_number,
                  customer_user_id, customer_display_name,
                  customer_email, customer_phone,
                  shipping_recipient_name, shipping_phone,
                  shipping_street_1, shipping_street_2,
                  shipping_city, shipping_state,
                  shipping_zip_code, shipping_country,
                  status, created_at, updated_at,
                  event_id, event_timestamp))
            cursor.close()
        finally:
            conn.close()

    def insert_order_items(self, order_id, items):
        """Batch insert order items.

        Args:
            order_id: The order ID.
            items: List of dicts with item data.
        """
        conn = get_database().get_connection()
        try:
            cursor = conn.cursor()
            for item in items:
                cursor.execute("""
                    INSERT INTO order_items
                        (order_id, item_id, product_id, supplier_id,
                         product_name, variant_name, variant_attributes_json,
                         image_url, supplier_name,
                         quantity, unit_price_cents, final_price_cents,
                         total_cents, fulfillment_status, shipped_quantity,
                         tracking_number, carrier, shipped_at, delivered_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        fulfillment_status=VALUES(fulfillment_status),
                        shipped_quantity=VALUES(shipped_quantity),
                        tracking_number=VALUES(tracking_number),
                        carrier=VALUES(carrier),
                        shipped_at=VALUES(shipped_at),
                        delivered_at=VALUES(delivered_at)
                """, (
                    order_id,
                    item["item_id"],
                    item["product_id"],
                    item["supplier_id"],
                    item["product_name"],
                    item.get("variant_name"),
                    json.dumps(item.get("variant_attributes", {})),
                    item.get("image_url"),
                    item.get("supplier_name"),
                    item["quantity"],
                    item["unit_price_cents"],
                    item["final_price_cents"],
                    item["total_cents"],
                    item.get("fulfillment_status", "pending"),
                    item.get("shipped_quantity", 0),
                    item.get("tracking_number"),
                    item.get("carrier"),
                    item.get("shipped_at"),
                    item.get("delivered_at"),
                ))
            cursor.close()
        finally:
            conn.close()

    def cancel_order(self, order_number, reason, event_id, event_timestamp):
        conn = get_database().get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE orders
                SET status = 'cancelled', cancelled_reason = %s,
                    event_id = %s, event_timestamp = %s
                WHERE order_number = %s
            """, (reason, event_id, event_timestamp, order_number))
            cursor.close()
        finally:
            conn.close()
