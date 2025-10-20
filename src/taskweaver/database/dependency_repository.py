"""Repository for CRUD operations in task_dependency table."""

from collections import deque
from pathlib import Path
from uuid import UUID

from loguru import logger

from .connection import DEFAULT_DB_PATH, get_connection
from .exceptions import DependencyError, TaskNotFoundError
from .models import TaskDependency, TaskStatus
from .repository import Task, TaskRepository
from .schema import DELETE_DEPENDENCY, INSERT_DEPENDENCY, SELECT_ACTIVE_BLOCKERS, SELECT_BLOCKED_TASKS


class TaskDependencyRepository:
    """Repository for Task Dependency table functions."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        """Initialize repository.

        Args:
            db_path: Path to SQLite database file.

        """
        self.db_path = db_path
        self.task_repository = TaskRepository()
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
        try:
            if any(
                self.task_repository.get_task(ids).status in ([TaskStatus.CANCELLED, TaskStatus.COMPLETED])  # type: ignore
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

    def remove_dependency(self, task_id: str, blocker_id: str) -> None:
        """Remove a dependency between two tasks.

        Args:
            task_id: UUID of the blocked task.
            blocker_id: UUID of the blocker task.

        Raises:
            DependencyError: If dependency does not exist.
        """
        logger.debug(f"Removing dependency: task-{task_id}, blocker-{blocker_id}")
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(DELETE_DEPENDENCY, (task_id, blocker_id))
            if not cursor.rowcount:
                logger.error(f"Cannot remove dependency: not found (task-{task_id}, blocker-{blocker_id})")
                raise DependencyError(f"Dependency not found: blocker-{blocker_id} -> task-{task_id}")
            conn.commit()
            logger.info(f"Removed dependency: task-{task_id}, blocker-{blocker_id}")

    def get_blockers(self, task_id: str) -> list[Task]:
        """Get all active tasks blocking this task.

        Args:
            task_id: UUID of the blocked task.

        Returns:
            List of Task objects that are blocking (status: pending/in_progress).
        """
        logger.debug(f"Retrieving active blockers for task: {task_id}")
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(SELECT_ACTIVE_BLOCKERS, (task_id,))
            rows = cursor.fetchall()

        blockers = [task for row in rows if (task := self.task_repository.get_task(task_id=row["blocker_id"]))]
        logger.debug(f"Found {len(blockers)} active blocker(s) for task {task_id}")
        return blockers

    def get_blocked(self, blocker_id: str) -> list[Task]:
        """Get all tasks blocked by this task.

        Args:
            blocker_id: UUID of the blocker task.

        Returns:
            List of Task objects that are blocked by this task.
        """
        logger.debug(f"Retrieving tasks blocked by: {blocker_id}")
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(SELECT_BLOCKED_TASKS, (blocker_id,))
            rows = cursor.fetchall()

        blocked = [task for row in rows if (task := self.task_repository.get_task(task_id=row["task_id"]))]
        logger.debug(f"Found {len(blocked)} blocked task(s) by {blocker_id}")
        return blocked

    def _cycle_check(self, task_id: str, blocker_id: str) -> bool:
        """Detect circular dependencies using BFS.

        Args:
            task_id: Task that would be blocked.
            blocker_id: Task that would block.

        Returns:
            True if adding dependency would create a cycle.
        """
        logger.debug(f"Checking for circular dependency: task-{task_id}, blocker-{blocker_id}")
        visited: set[str] = set()
        queue: deque[str] = deque([blocker_id])

        while queue:
            current = queue.popleft()
            if current == task_id:
                logger.warning(f"Circular dependency detected: task-{task_id} -> blocker-{blocker_id}")
                return True
            if current in visited:
                continue
            visited.add(current)
            queue.extend(str(blocked.task_id) for blocked in self.get_blocked(current))

        logger.debug(f"No circular dependency found for task-{task_id}, blocker-{blocker_id}")
        return False
