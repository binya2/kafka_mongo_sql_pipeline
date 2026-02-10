"""Data Access Layer for users table."""

import logging

from src.db.connection import get_database

logger = logging.getLogger(__name__)


class UserDAL:

    def insert_user(self, user_id, email, phone, display_name, avatar, bio,
                    version, deleted_at, created_at, updated_at,
                    event_id, event_timestamp):
        """Insert a new user into the users table."""
        connection = get_database().get_connection()
        cursor = connection.cursor()
        try:
            insert_query = """
                           INSERT INTO users (user_id, email, phone, display_name, avatar, bio,
                                              version, deleted_at, created_at, updated_at,
                                              event_id, event_timestamp)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                           ON DUPLICATE KEY UPDATE email           = VALUES(email),
                                                   phone           = VALUES(phone),
                                                   display_name    = VALUES(display_name),
                                                   avatar          = VALUES(avatar),
                                                   bio             = VALUES(bio),
                                                   version         = VALUES(version),
                                                   deleted_at      = VALUES(deleted_at),
                                                   updated_at      = VALUES(updated_at),
                                                   event_id        = VALUES(event_id),
                                                   event_timestamp = VALUES(event_timestamp)
                           """

            values = (user_id, email, phone, display_name, avatar, bio, version, deleted_at, created_at, updated_at,
                      event_id, event_timestamp)

            cursor.execute(insert_query, values)
            connection.commit()
            logger.info(f"Inserted/Updated user {display_name} with ID {user_id}")
        except Exception as e:
            connection.rollback()
            logger.error(f"Error inserting/updating user {display_name}: {e}")
            raise
        finally:
            cursor.close()
            connection.close()

    def soft_delete_user(self, user_id, event_id, event_timestamp):
        """Soft delete a user by setting the deleted_at timestamp."""
        connection = get_database().get_connection()
        cursor = connection.cursor()
        try:
            soft_delete_query = """
                                UPDATE users
                                SET deleted_at      = NOW(),
                                    event_id        = %s,
                                    event_timestamp = %s
                                WHERE user_id = %s
                                """
            cursor.execute(soft_delete_query, (event_id, event_timestamp, user_id))
            connection.commit()
            logger.info(f"Soft deleted user with ID {user_id}")
        except Exception as e:
            connection.rollback()
            logger.error(f"Error soft deleting user with ID {user_id}: {e}")
            raise
        finally:
            cursor.close()
            connection.close()
