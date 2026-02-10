"""MySQL database connection pool."""

import logging

from mysql.connector import pooling

from src.config import mysql_config
from src.db.tables import TABLE_DEFINITIONS

logger = logging.getLogger(__name__)


class Database:
    """MySQL connection pool manager."""

    def __init__(self):
        self._pool = None

    def connect(self):
        try:
            config_data = mysql_config.model_dump()
            self._pool = pooling.MySQLConnectionPool(**config_data)
            logger.info("Connection pool created successfully")
        except Exception as e:
            logger.error(f"Error creating connection pool: {e}")
            raise

    def init_tables(self):
        connection = self.get_connection()
        cursor = connection.cursor()
        try:
            for schema in TABLE_DEFINITIONS:
                cursor.execute(schema)
                table_name = schema.split('EXISTS')[1].split('(')[0].strip()
                logger.info(f"Table '{table_name}' ensured in database")
            cursor.close()
        except Exception as e:
            cursor.close()
            logger.error(f"Error initializing tables: {e}")
            raise
        finally:
            connection.close()

    def get_connection(self):
        return self._pool.get_connection()


_db = None


def get_database() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db
