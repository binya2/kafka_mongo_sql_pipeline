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
        """Insert a new order into the orders table."""
        connection = get_database().get_connection()
        cursor = connection.cursor()
        try:
            insert_query = """
                           INSERT INTO orders (order_id, order_number, customer_user_id, customer_display_name,
                                               customer_email, customer_phone, shipping_recipient_name,
                                               shipping_phone, shipping_street_1, shipping_street_2,
                                               shipping_city, shipping_state, shipping_zip_code,
                                               shipping_country, status, created_at, updated_at,
                                               event_id, event_timestamp)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                           ON DUPLICATE KEY UPDATE customer_user_id        = VALUES(customer_user_id),
                                                   customer_display_name   = VALUES(customer_display_name),
                                                   customer_email          = VALUES(customer_email),
                                                   customer_phone          = VALUES(customer_phone),
                                                   shipping_recipient_name = VALUES(shipping_recipient_name),
                                                   shipping_phone          = VALUES(shipping_phone),
                                                   shipping_street_1       = VALUES(shipping_street_1),
                                                   shipping_street_2       = VALUES(shipping_street_2),
                                                   shipping_city           = VALUES(shipping_city),
                                                   shipping_state          = VALUES(shipping_state),
                                                   shipping_zip_code       = VALUES(shipping_zip_code),
                                                   shipping_country        = VALUES(shipping_country),
                                                   status                  = VALUES(status),
                                                   created_at              = VALUES(created_at),
                                                   updated_at              = VALUES(updated_at),
                                                   event_id                = VALUES(event_id),
                                                   event_timestamp         = VALUES(event_timestamp) \
                           """

            cursor.execute(insert_query, (
                order_id, order_number, customer_user_id, customer_display_name,
                customer_email, customer_phone, shipping_recipient_name,
                shipping_phone, shipping_street_1, shipping_street_2,
                shipping_city, shipping_state, shipping_zip_code,
                shipping_country, status, created_at, updated_at,
                event_id, event_timestamp
            ))
            connection.commit()
            logger.info(f"Inserted order {order_number} with ID {order_id}")

        except Exception as e:
            connection.rollback()
            logger.error(f"Error inserting order {order_number}: {e}")
            raise
        finally:
            cursor.close()
            connection.close()

    def insert_order_items(self, order_id, items: list):
        """Batch insert order items.

        Args:
            order_id: The order ID.
            items: List of dicts with item data.
        """
        connection = get_database().get_connection()
        cursor = connection.cursor()
        try:
            insert_query = """
                           INSERT INTO order_items (order_id, item_id, product_id, supplier_id,
                                                    product_name, variant_name, variant_attributes_json,
                                                    image_url, supplier_name,
                                                    quantity, unit_price_cents, final_price_cents,
                                                    total_cents, fulfillment_status, shipped_quantity,
                                                    tracking_number, carrier, shipped_at, delivered_at)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                           ON DUPLICATE KEY UPDATE fulfillment_status = VALUES(fulfillment_status),
                                                   shipped_quantity   = VALUES(shipped_quantity),
                                                   tracking_number    = VALUES(tracking_number),
                                                   carrier            = VALUES(carrier),
                                                   shipped_at         = VALUES(shipped_at),
                                                   delivered_at       = VALUES(delivered_at) \
                           """

            values_to_insert = []
            for item in items:
                row = (
                    order_id,
                    item['item_id'],
                    item['product_id'],
                    item['supplier_id'],
                    item['product_name'],
                    item['variant_name'],
                    json.dumps(item.get("variant_attributes", {})),
                    item['image_url'],
                    item['supplier_name'],
                    item['quantity'],
                    item['unit_price_cents'],
                    item['final_price_cents'],
                    item['total_cents'],
                    item.get("fulfillment_status", "pending"),
                    item['shipped_quantity'],
                    item['tracking_number'],
                    item['carrier'],
                    item['shipped_at'],
                    item['delivered_at']
                )
                values_to_insert.append(row)

            if values_to_insert:
                cursor.executemany(insert_query, values_to_insert)
                connection.commit()
                logger.info(f"Inserted/Updated {len(values_to_insert)} items for order ID {order_id}")

        except Exception as e:
            connection.rollback()
            logger.error(f"Error inserting/updating items for order ID {order_id}: {e}")
            raise
        finally:
            cursor.close()
            connection.close()

    def cancel_order(self, order_number, event_id, event_timestamp):
        """Mark an order as cancelled."""
        connection = get_database().get_connection()
        cursor = connection.cursor()
        try:
            update_query = """
                           UPDATE orders
                           SET status          = 'cancelled',
                               event_id        = %s,
                               event_timestamp = %s
                           WHERE order_number = %s \
                           """
            cursor.execute(update_query, (event_id, event_timestamp, order_number))
            connection.commit()
            logger.info(f"Cancelled order {order_number}")
        except Exception as e:
            connection.rollback()
            logger.error(f"Error cancelling order {order_number}: {e}")
            raise
        finally:
            cursor.close()
            connection.close()
