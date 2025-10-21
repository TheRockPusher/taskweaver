"""Database connection management."""

import sqlite3
from collections.abc import Generator
from contextlib import closing, contextmanager
from pathlib import Path

from loguru import logger

from ..config import get_paths
from .schema import (
    CREATE_DEPENDENCY_INDEX_BLOCKER,
    CREATE_DEPENDENCY_INDEX_TASK,
    CREATE_DEPENDENCY_TABLE,
    CREATE_SCHEMA_VERSION_TABLE,
    CREATE_TASKS_INDEX_ID,
    CREATE_TASKS_INDEX_STATUS,
    CREATE_TASKS_TABLE,
    CREATE_VIEW_TASKS_FULL,
    INSERT_SCHEMA_VERSION,
    SCHEMA_VERSION,
)

# Default database location (XDG-compliant)
DEFAULT_DB_PATH = get_paths().database_file


def init_database(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Initialize database with schema.

    Args:
        db_path: Path to SQLite database file.

    """
    logger.debug(f"Initializing database at: {db_path}")
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(db_path)) as conn:
        with conn:  # Transaction management
            # Create tables and indexes separately
            logger.debug("Creating tasks table")
            conn.execute(CREATE_TASKS_TABLE)
            conn.execute(CREATE_TASKS_INDEX_ID)
            conn.execute(CREATE_TASKS_INDEX_STATUS)

            logger.debug("Creating schema_version table")
            conn.execute(CREATE_SCHEMA_VERSION_TABLE)
            conn.execute(INSERT_SCHEMA_VERSION, (SCHEMA_VERSION,))

            logger.debug("Creating dependency table")
            conn.execute(CREATE_DEPENDENCY_TABLE)
            conn.execute(CREATE_DEPENDENCY_INDEX_TASK)
            conn.execute(CREATE_DEPENDENCY_INDEX_BLOCKER)

            logger.debug("Create Views")
            conn.execute(CREATE_VIEW_TASKS_FULL)

            # Transaction auto-commits on successful exit
        logger.info(f"Database initialized successfully at {db_path} (schema version: {SCHEMA_VERSION})")


def _ensure_database_exists(db_path: Path) -> None:
    """Ensure database file and schema exist, initialize if needed.

    Args:
        db_path: Path to SQLite database file.

    """
    if not db_path.exists():
        logger.debug(f"Database does not exist, initializing: {db_path}")
        init_database(db_path)


@contextmanager
def get_connection(db_path: Path = DEFAULT_DB_PATH) -> Generator[sqlite3.Connection]:
    """Get database connection as context manager.

    Automatically initializes the database if it doesn't exist.

    Args:
        db_path: Path to SQLite database file.

    Yields:
        SQLite connection with row factory set.

    Example:
        >>> with get_connection() as conn:
        ...     cursor = conn.execute("SELECT * FROM tasks")
        ...     tasks = cursor.fetchall()

    """
    # Ensure database exists before attempting connection
    _ensure_database_exists(db_path)

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
