"""Data Access Layer for suppliers table."""

import logging

from src.db.connection import get_database

logger = logging.getLogger(__name__)


class SupplierDAL:

    def insert_supplier(self, supplier_id, email, primary_phone,
                        contact_person_name, contact_person_title,
                        contact_person_email, contact_person_phone,
                        legal_name, dba_name,
                        street_address_1, street_address_2,
                        city, state, zip_code, country,
                        support_email, support_phone,
                        facebook_url, instagram_handle,
                        twitter_handle, linkedin_url, timezone,
                        created_at, updated_at,
                        event_id, event_timestamp):
        """Insert a new supplier into the suppliers table."""
        connection = get_database().get_connection()
        cursor = connection.cursor()
        try:
            insert_query = """
                           INSERT INTO suppliers (supplier_id, email, primary_phone,
                                                  contact_person_name, contact_person_title,
                                                  contact_person_email, contact_person_phone,
                                                  legal_name, dba_name,
                                                  street_address_1, street_address_2,
                                                  city, state, zip_code, country,
                                                  support_email, support_phone,
                                                  facebook_url, instagram_handle,
                                                  twitter_handle, linkedin_url, timezone,
                                                  created_at, updated_at,
                                                  event_id, event_timestamp)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                   %s, %s, %s) ON DUPLICATE KEY
                           UPDATE
                               email =
                           VALUES (email), primary_phone =
                           VALUES (primary_phone), contact_person_name =
                           VALUES (contact_person_name), contact_person_title =
                           VALUES (contact_person_title), contact_person_email =
                           VALUES (contact_person_email), contact_person_phone =
                           VALUES (contact_person_phone), legal_name =
                           VALUES (legal_name), dba_name =
                           VALUES (dba_name), street_address_1 =
                           VALUES (street_address_1), street_address_2 =
                           VALUES
                               (street_address_2), city =
                           VALUES (city), state =
                           VALUES (state), zip_code =
                           VALUES (zip_code), country =
                           VALUES (country), support_email =
                           VALUES (support_email), support_phone =
                           VALUES (support_phone), facebook_url =
                           VALUES (facebook_url), instagram_handle =
                           VALUES (instagram_handle), twitter_handle =
                           VALUES (twitter_handle), linkedin_url =
                           VALUES (linkedin_url), timezone =
                           VALUES (timezone), created_at =
                           VALUES (created_at), updated_at =
                           VALUES (updated_at), event_id =
                           VALUES (event_id), event_timestamp =
                           VALUES (event_timestamp)
                           """
            value = (
                supplier_id, email, primary_phone,
                contact_person_name, contact_person_title,
                contact_person_email, contact_person_phone,
                legal_name, dba_name,
                street_address_1, street_address_2,
                city, state, zip_code, country,
                support_email, support_phone,
                facebook_url, instagram_handle,
                twitter_handle, linkedin_url, timezone,
                created_at, updated_at,
                event_id, event_timestamp
            )
            cursor.execute(insert_query, value)
            connection.commit()
            logger.info(f"Inserted/Updated supplier with ID {supplier_id}")
        except Exception as e:
            connection.rollback()
            logger.error(f"Error inserting/updating supplier with ID {supplier_id}: {e}")
            raise
        finally:
            cursor.close()
            connection.close()

    def delete_supplier(self, supplier_id):
        """Delete a supplier from the suppliers table."""
        connection = get_database().get_connection()
        cursor = connection.cursor()
        try:
            delete_query = "DELETE FROM suppliers WHERE supplier_id = %s"
            cursor.execute(delete_query, (supplier_id,))
            connection.commit()
            logger.info(f"Deleted supplier with ID {supplier_id}")
        except Exception as e:
            connection.rollback()
            logger.error(f"Error deleting supplier with ID {supplier_id}: {e}")
            raise
        finally:
            cursor.close()
            connection.close()
