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
        """Insert or update a product in the products table."""
        connection = get_database().get_connection()
        cursor = connection.cursor()
        try:
            upsert_query = """
                           INSERT INTO products (product_id, supplier_id, supplier_name,
                                                 name, short_description, category, unit_type,
                                                 base_sku, brand, base_price_cents, status,
                                                 view_count, favorite_count, purchase_count,
                                                 total_reviews, published_at, created_at, updated_at,
                                                 event_id, event_timestamp)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                           ON DUPLICATE KEY UPDATE supplier_id       = VALUES(supplier_id),
                                                   supplier_name     = VALUES(supplier_name),
                                                   name              = VALUES(name),
                                                   short_description = VALUES(short_description),
                                                   category          = VALUES(category),
                                                   unit_type         = VALUES(unit_type),
                                                   base_sku          = VALUES(base_sku),
                                                   brand             = VALUES(brand),
                                                   base_price_cents  = VALUES(base_price_cents),
                                                   status            = VALUES(status),
                                                   view_count        = VALUES(view_count),
                                                   favorite_count    = VALUES(favorite_count),
                                                   purchase_count    = VALUES(purchase_count),
                                                   total_reviews     = VALUES(total_reviews),
                                                   published_at      = VALUES(published_at),
                                                   updated_at        = VALUES(updated_at),
                                                   event_id          = VALUES(event_id),
                                                   event_timestamp   = VALUES(event_timestamp)
                           """

            value = (product_id, supplier_id, supplier_name,
                     name, short_description, category, unit_type,
                     base_sku, brand, base_price_cents, status,
                     view_count, favorite_count, purchase_count,
                     total_reviews, published_at, created_at, updated_at,
                     event_id, event_timestamp)

            cursor.execute(upsert_query, value)
            connection.commit()
            logger.info(f"Upserted product with ID {product_id}")
        except Exception as e:
            connection.rollback()
            logger.error(f"Error upserting product with ID {product_id}: {e}")
            raise
        finally:
            cursor.close()
            connection.close()

    def replace_variants(self, product_id, variants):
        """Delete existing variants and insert new ones.

        Args:
            product_id: The product ID.
            variants: List of dicts with variant data.
        """
        connection = get_database().get_connection()
        cursor = connection.cursor()
        try:
            delete_query = "DELETE FROM product_variants WHERE product_id = %s"
            cursor.execute(delete_query, (product_id,))
            logger.info(f"Deleted existing variants for product ID {product_id}")

            if variants:
                insert_query = """
                               INSERT INTO product_variants
                               (product_id, variant_key, variant_id, variant_name,
                                attributes_json, price_cents, cost_cents, quantity,
                                width_cm, height_cm, depth_cm)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                               """

                values_to_insert = []
                for variant in variants:
                    row = (
                        product_id,
                        variant['variant_key'],
                        variant['variant_id'],
                        variant['variant_name'],
                        json.dumps(variant.get("attributes", {})),
                        variant['price_cents'],
                        variant.get('cost_cents'),
                        variant.get('quantity', 0),
                        variant.get('width_cm'),
                        variant.get('height_cm'),
                        variant.get('depth_cm')
                    )
                    values_to_insert.append(row)

                cursor.executemany(insert_query, values_to_insert)

            connection.commit()
            logger.info(f"Inserted {len(variants)} variants for product ID {product_id}")
        except Exception as e:
            connection.rollback()
            logger.error(f"Error replacing variants for product ID {product_id}: {e}")
            raise
        finally:
            cursor.close()
            connection.close()

    def delete_product(self, product_id):
        """Delete a product and its variants."""
        connection = get_database().get_connection()
        cursor = connection.cursor()
        try:
            delete_query = "DELETE FROM products WHERE product_id = %s"
            cursor.execute(delete_query, (product_id,))
            connection.commit()
            logger.info(f"Deleted product with ID {product_id} and its variants")
        except Exception as e:
            connection.rollback()
            logger.error(f"Error deleting product with ID {product_id}: {e}")
            raise
        finally:
            cursor.close()
            connection.close()
