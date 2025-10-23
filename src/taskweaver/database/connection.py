"""Database connection management for SQLite and Qdrant."""

import sqlite3
from collections.abc import Generator
from contextlib import closing, contextmanager
from pathlib import Path

from loguru import logger
from qdrant_client import QdrantClient

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

# Default database locations (XDG-compliant)
DEFAULT_DB_PATH = get_paths().database_file
DEFAULT_QDRANT_PATH = get_paths().qdrant_dir


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


def _ensure_databases_exist(db_path: Path, qdrant_path: Path) -> None:
    """Ensure both SQLite and Qdrant databases exist, initialize if needed.

    Args:
        db_path: Path to SQLite database file.
        qdrant_path: Path to Qdrant storage directory.

    """
    # Initialize SQLite if missing
    if not db_path.exists():
        logger.debug(f"SQLite database does not exist, initializing: {db_path}")
        init_database(db_path)

    # Initialize Qdrant if missing
    if not qdrant_path.exists():
        logger.debug(f"Qdrant directory does not exist, initializing: {qdrant_path}")
        init_qdrant(qdrant_path)


@contextmanager
def get_connection(
    db_path: Path = DEFAULT_DB_PATH,
    qdrant_path: Path = DEFAULT_QDRANT_PATH,
) -> Generator[sqlite3.Connection]:
    """Get database connection as context manager.

    Automatically initializes both SQLite and Qdrant if they don't exist.

    Args:
        db_path: Path to SQLite database file.
        qdrant_path: Path to Qdrant storage directory.

    Yields:
        SQLite connection with row factory set.

    Example:
        >>> with get_connection() as conn:
        ...     cursor = conn.execute("SELECT * FROM tasks")
        ...     tasks = cursor.fetchall()

    """
    # Ensure both databases exist before attempting connection
    _ensure_databases_exist(db_path, qdrant_path)

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


def init_qdrant(qdrant_path: Path = DEFAULT_QDRANT_PATH) -> None:
    """Initialize Qdrant vector database.

    Creates the Qdrant storage directory and initializes the client.
    Qdrant will create collections on-demand when first used.

    Args:
        qdrant_path: Path to Qdrant storage directory.

    Example:
        >>> from taskweaver.database.connection import init_qdrant
        >>> init_qdrant()  # Initializes at ~/.local/share/taskweaver/qdrant_store
    """
    logger.debug(f"Initializing Qdrant at: {qdrant_path}")
    qdrant_path.mkdir(parents=True, exist_ok=True)

    # Verify Qdrant can initialize (creates internal data structures)
    _ = QdrantClient(path=str(qdrant_path))
    logger.info(f"Qdrant initialized successfully at {qdrant_path}")


@contextmanager
def get_qdrant_client(
    qdrant_path: Path = DEFAULT_QDRANT_PATH,
    db_path: Path = DEFAULT_DB_PATH,
) -> Generator[QdrantClient]:
    """Get Qdrant client as context manager.

    Automatically initializes both SQLite and Qdrant if they don't exist.

    Args:
        qdrant_path: Path to Qdrant storage directory.
        db_path: Path to SQLite database file.

    Yields:
        QdrantClient instance.

    Example:
        >>> with get_qdrant_client() as client:
        ...     collections = client.get_collections()
    """
    # Ensure both databases exist (unified initialization)
    _ensure_databases_exist(db_path, qdrant_path)

    logger.debug(f"Opening Qdrant client: {qdrant_path}")
    client = QdrantClient(path=str(qdrant_path))
    try:
        yield client
    except Exception as e:
        logger.error(f"Qdrant operation failed: {e}")
        raise
    finally:
        logger.debug("Closing Qdrant client")
        client.close()
