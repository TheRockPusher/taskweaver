"""Database connection management."""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from loguru import logger

from .schema import (
    CREATE_SCHEMA_VERSION_TABLE,
    CREATE_TASKS_TABLE,
    INSERT_SCHEMA_VERSION,
    SCHEMA_VERSION,
)

# Default database location
DEFAULT_DB_PATH = Path.home() / ".taskweaver" / "tasks.db"


def init_database(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Initialize database with schema.

    Args:
        db_path: Path to SQLite database file.

    """
    logger.debug(f"Initializing database at: {db_path}")
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        # Create tables
        logger.debug("Creating tasks table")
        conn.execute(CREATE_TASKS_TABLE)
        logger.debug("Creating schema_version table")
        conn.execute(CREATE_SCHEMA_VERSION_TABLE)
        conn.execute(INSERT_SCHEMA_VERSION, (SCHEMA_VERSION,))
        conn.commit()
        logger.info(f"Database initialized successfully at {db_path} (schema version: {SCHEMA_VERSION})")


@contextmanager
def get_connection(db_path: Path = DEFAULT_DB_PATH) -> Generator[sqlite3.Connection]:
    """Get database connection as context manager.

    Args:
        db_path: Path to SQLite database file.

    Yields:
        SQLite connection with row factory set.

    Example:
        >>> with get_connection() as conn:
        ...     cursor = conn.execute("SELECT * FROM tasks")
        ...     tasks = cursor.fetchall()

    """
    logger.debug(f"Opening database connection: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Access columns by name
    try:
        yield conn
    except Exception as e:
        logger.error(f"Database operation failed: {e}")
        raise
    finally:
        logger.debug("Closing database connection")
        conn.close()
