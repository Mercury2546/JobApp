"""
SQLite Database manager and connection handlers.
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator
from config.settings import DB_PATH, BASE_DIR
from utils.logger import setup_logger

logger = setup_logger("database")
SCHEMA_PATH = BASE_DIR / "database" / "schema.sql"


@contextmanager
def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager that yields an active SQLite connection.
    Enables foreign keys and returns rows as dictionary-like objects (sqlite3.Row).
    Automatically commits on success or rolls back on exception.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        yield conn
        conn.commit()
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error occurred: {e}", exc_info=True)
        raise
    finally:
        if conn:
            conn.close()


def init_db() -> bool:
    """
    Initializes the SQLite database tables using schema.sql.
    Safe to run repeatedly (uses CREATE TABLE IF NOT EXISTS).
    """
    if not SCHEMA_PATH.exists():
        logger.error(f"Schema file not found at: {SCHEMA_PATH}")
        raise FileNotFoundError(f"Missing schema file: {SCHEMA_PATH}")

    try:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as schema_file:
            schema_sql = schema_file.read()

        with get_db_connection() as conn:
            conn.executescript(schema_sql)

        logger.info(f"Database initialized successfully at: {DB_PATH}")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        raise


def check_db_health() -> bool:
    """
    Performs a lightweight sanity check on the database.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1;")
            result = cursor.fetchone()
            return result is not None and result[0] == 1
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        return False
