"""MySQL database connection pool."""

import os
import logging

from mysql.connector import pooling

logger = logging.getLogger(__name__)


class Database:
    """MySQL connection pool manager."""

    def __init__(self):
        self._pool = None

    def connect(self):
        self._pool = pooling.MySQLConnectionPool(
            pool_name="analytics_pool",
            pool_size=5,
            host=os.getenv("MYSQL_HOST", "localhost"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.getenv("MYSQL_USER", "analytics"),
            password=os.getenv("MYSQL_PASSWORD", "analytics123"),
            database=os.getenv("MYSQL_DATABASE", "analytics"),
            autocommit=True,
        )
        logger.info("MySQL connection pool created")

    def init_tables(self):
        from src.db.tables import TABLE_DEFINITIONS

        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            for ddl in TABLE_DEFINITIONS:
                cursor.execute(ddl)
            cursor.close()
            logger.info("All tables initialized")
        finally:
            conn.close()

    def get_connection(self):
        return self._pool.get_connection()


_db = None


def get_database() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db
