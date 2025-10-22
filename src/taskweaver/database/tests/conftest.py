"""Pytest fixtures for database tests."""

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from taskweaver.database.connection import init_database
from taskweaver.database.dependency_repository import TaskDependencyRepository
from taskweaver.database.repository import TaskRepository


@pytest.fixture
def temp_db() -> Generator[Path]:
    """Create temporary database for testing.

    Yields:
        Path to temporary database file.

    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    init_database(db_path)
    yield db_path

    # Cleanup
    db_path.unlink(missing_ok=True)


@pytest.fixture
def task_repo(temp_db: Path) -> TaskRepository:
    """Create task repository with temporary database.

    Args:
        temp_db: Temporary database path.

    Returns:
        TaskRepository instance.

    """
    return TaskRepository(db_path=temp_db)


@pytest.fixture
def dep_repo(temp_db: Path) -> TaskDependencyRepository:
    """Create dependency repository with temporary database.

    Args:
        temp_db: Temporary database path.

    Returns:
        TaskDependencyRepository instance.

    """
    return TaskDependencyRepository(db_path=temp_db)


@pytest.fixture
def sample_task_data() -> dict:
    """Provide sample task creation data with all required fields.

    Returns:
        Dictionary with all fields needed for TaskCreate.

    """
    return {
        "title": "Sample task",
        "description": "Sample description",
        "duration_min": 30,
        "llm_value": 5.0,
        "requirement": "Sample requirement",
    }
