"""Repository for CRUD operations in task_dependency table."""

from pathlib import Path
from uuid import UUID

from loguru import logger

from .connection import DEFAULT_DB_PATH, get_connection
from .exceptions import DependencyError, TaskNotFoundError
from .models import TaskDependency, TaskStatus
from .repository import TaskRepository
from .schema import INSERT_DEPENDENCY


class TaskDependencyRepository:
    """Repository for Task Dependency table functions."""
    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        """Initialize repository.

        Args:
            db_path: Path to SQLite database file.

        """
        self.db_path = db_path
        logger.debug(f"TaskRepository initialized with database: {db_path}")

    def add_dependency(self, task_id: UUID, blocker_id: UUID) -> TaskDependency:
        """Create a dependency between two tasks.

        Args:
            task_id: UUID of the task that is blocked.
            blocker_id: UUID of the task that blocks completion.

        Returns:
            Created TaskDependency.

        Raises:
            TaskNotFoundError: If either task doesn't exist.
            DependencyError: If either task is already closed (completed/cancelled).
        """
        repository = TaskRepository()
        try:
            if any(
                repository.get_task(ids).status in ([TaskStatus.CANCELLED, TaskStatus.COMPLETED]) # type: ignore
                for ids in [task_id, blocker_id]
            ):  # type: ignore fail fast
                raise DependencyError("task is closed")
        except KeyError as exc:
            raise TaskNotFoundError(task_id) from exc

        dependency = TaskDependency(task_id=task_id, blocker_id=blocker_id)
        with get_connection(self.db_path) as conn:
            conn.execute(
                INSERT_DEPENDENCY,
                (dependency.dependency_id, dependency.task_id, dependency.blocker_id, dependency.created_at),
            )
            conn.commit()
            logger.info(f"Created dependency: task-{dependency.dependency_id}, blocker-{dependency.blocker_id}")
        return dependency
