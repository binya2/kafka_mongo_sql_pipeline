"""Data Access Layer for users table."""

import logging

from src.db.connection import get_database

logger = logging.getLogger(__name__)


class UserDAL:

    def insert_user(self, user_id, email, phone, display_name, avatar, bio,
                    version, deleted_at, created_at, updated_at,
                    event_id, event_timestamp):
        conn = get_database().get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users
                    (user_id, email, phone, display_name, avatar, bio,
                     version, deleted_at, created_at, updated_at,
                     event_id, event_timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    email=VALUES(email), phone=VALUES(phone),
                    display_name=VALUES(display_name), avatar=VALUES(avatar),
                    bio=VALUES(bio), version=VALUES(version),
                    deleted_at=VALUES(deleted_at), updated_at=VALUES(updated_at),
                    event_id=VALUES(event_id), event_timestamp=VALUES(event_timestamp)
            """, (user_id, email, phone, display_name, avatar, bio,
                  version, deleted_at, created_at, updated_at,
                  event_id, event_timestamp))
            cursor.close()
        finally:
            conn.close()

    def soft_delete_user(self, user_id, event_id, event_timestamp):
        conn = get_database().get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users SET deleted_at = NOW(6),
                    event_id = %s, event_timestamp = %s
                WHERE user_id = %s
            """, (event_id, event_timestamp, user_id))
            cursor.close()
        finally:
            conn.close()
