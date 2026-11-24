"""
SQLite Database manager and connection handlers.
"""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager

from config.settings import BASE_DIR, DB_PATH
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
    except sqlite3.Error:
        if conn:
            conn.rollback()
        logger.exception("Database error occurred")
        raise
    finally:
        if conn:
            conn.close()


def migrate_db():
    """
    Safely adds missing columns to existing tables without data loss.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(applications);")
            columns = [row["name"] for row in cursor.fetchall()]

            new_columns = [
                ("email_subject", "TEXT"),
                ("email_content", "TEXT"),
                ("follow_up_date", "TEXT"),
                ("image_url", "TEXT"),
            ]

            for col_name, col_type in new_columns:
                if col_name not in columns:
                    cursor.execute(
                        f"ALTER TABLE applications ADD COLUMN {col_name} {col_type};"
                    )
                    logger.info(f"Added column {col_name} to applications table.")

            # Migrate resumes table
            cursor.execute("PRAGMA table_info(resumes);")
            res_columns = [row["name"] for row in cursor.fetchall()]
            if "rewritten_text" not in res_columns:
                cursor.execute("ALTER TABLE resumes ADD COLUMN rewritten_text TEXT;")
                logger.info("Added column rewritten_text to resumes table.")
    except sqlite3.Error as e:
        logger.warning(f"Migration notice: {e}")


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

        # Run safe migrations for existing installations
        migrate_db()

        logger.info(f"Database initialized successfully at: {DB_PATH}")
        return True
    except Exception:
        logger.exception("Failed to initialize database")
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
    except sqlite3.Error as e:
        logger.warning(f"Database health check failed: {e}")
        return False
