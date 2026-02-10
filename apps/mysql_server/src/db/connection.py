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
        # TODO: Implement (TASK_00)
        pass

    def init_tables(self):
        # TODO: Implement (TASK_00)
        pass

    def get_connection(self):
        # TODO: Implement (TASK_00)
        pass


_db = None


def get_database() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db
