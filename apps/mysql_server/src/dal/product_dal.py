"""Data Access Layer for products and product_variants tables."""

import json
import logging

from src.db.connection import get_database

logger = logging.getLogger(__name__)


class ProductDAL:

    def upsert_product(self, product_id, supplier_id, supplier_name,
                       name, short_description, category, unit_type,
                       base_sku, brand, base_price_cents, status,
                       view_count, favorite_count, purchase_count,
                       total_reviews, published_at, created_at, updated_at,
                       event_id, event_timestamp):
        conn = get_database().get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO products
                    (product_id, supplier_id, supplier_name,
                     name, short_description, category, unit_type,
                     base_sku, brand, base_price_cents, status,
                     view_count, favorite_count, purchase_count,
                     total_reviews, published_at, created_at, updated_at,
                     event_id, event_timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    supplier_name=VALUES(supplier_name),
                    name=VALUES(name),
                    short_description=VALUES(short_description),
                    category=VALUES(category), unit_type=VALUES(unit_type),
                    base_sku=VALUES(base_sku), brand=VALUES(brand),
                    base_price_cents=VALUES(base_price_cents),
                    status=VALUES(status),
                    view_count=VALUES(view_count),
                    favorite_count=VALUES(favorite_count),
                    purchase_count=VALUES(purchase_count),
                    total_reviews=VALUES(total_reviews),
                    published_at=VALUES(published_at),
                    updated_at=VALUES(updated_at),
                    event_id=VALUES(event_id),
                    event_timestamp=VALUES(event_timestamp)
            """, (product_id, supplier_id, supplier_name,
                  name, short_description, category, unit_type,
                  base_sku, brand, base_price_cents, status,
                  view_count, favorite_count, purchase_count,
                  total_reviews, published_at, created_at, updated_at,
                  event_id, event_timestamp))
            cursor.close()
        finally:
            conn.close()

    def replace_variants(self, product_id, variants):
        """Delete existing variants and insert new ones.

        Args:
            product_id: The product ID.
            variants: List of dicts with variant data.
        """
        conn = get_database().get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM product_variants WHERE product_id = %s",
                (product_id,),
            )
            for v in variants:
                cursor.execute("""
                    INSERT INTO product_variants
                        (product_id, variant_key, variant_id, variant_name,
                         attributes_json, price_cents, cost_cents, quantity,
                         width_cm, height_cm, depth_cm, image_url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    product_id,
                    v["variant_key"],
                    v["variant_id"],
                    v["variant_name"],
                    json.dumps(v["attributes"]),
                    v["price_cents"],
                    v.get("cost_cents"),
                    v.get("quantity", 0),
                    v.get("width_cm"),
                    v.get("height_cm"),
                    v.get("depth_cm"),
                    v.get("image_url"),
                ))
            cursor.close()
        finally:
            conn.close()

    def delete_product(self, product_id):
        conn = get_database().get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM products WHERE product_id = %s",
                           (product_id,))
            cursor.close()
        finally:
            conn.close()
