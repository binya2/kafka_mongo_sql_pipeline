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
        conn = get_database().get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO suppliers
                    (supplier_id, email, primary_phone,
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
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    email=VALUES(email), primary_phone=VALUES(primary_phone),
                    contact_person_name=VALUES(contact_person_name),
                    contact_person_title=VALUES(contact_person_title),
                    contact_person_email=VALUES(contact_person_email),
                    contact_person_phone=VALUES(contact_person_phone),
                    legal_name=VALUES(legal_name), dba_name=VALUES(dba_name),
                    street_address_1=VALUES(street_address_1),
                    street_address_2=VALUES(street_address_2),
                    city=VALUES(city), state=VALUES(state),
                    zip_code=VALUES(zip_code), country=VALUES(country),
                    support_email=VALUES(support_email),
                    support_phone=VALUES(support_phone),
                    facebook_url=VALUES(facebook_url),
                    instagram_handle=VALUES(instagram_handle),
                    twitter_handle=VALUES(twitter_handle),
                    linkedin_url=VALUES(linkedin_url),
                    timezone=VALUES(timezone),
                    updated_at=VALUES(updated_at),
                    event_id=VALUES(event_id),
                    event_timestamp=VALUES(event_timestamp)
            """, (supplier_id, email, primary_phone,
                  contact_person_name, contact_person_title,
                  contact_person_email, contact_person_phone,
                  legal_name, dba_name,
                  street_address_1, street_address_2,
                  city, state, zip_code, country,
                  support_email, support_phone,
                  facebook_url, instagram_handle,
                  twitter_handle, linkedin_url, timezone,
                  created_at, updated_at,
                  event_id, event_timestamp))
            cursor.close()
        finally:
            conn.close()

    def delete_supplier(self, supplier_id):
        conn = get_database().get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM suppliers WHERE supplier_id = %s",
                           (supplier_id,))
            cursor.close()
        finally:
            conn.close()
