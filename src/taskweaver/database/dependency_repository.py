"""Repository for CRUD operations in task_dependency table."""

from collections import deque
from pathlib import Path
from uuid import UUID

from loguru import logger

from .connection import DEFAULT_DB_PATH, get_connection
from .exceptions import DependencyError, TaskNotFoundError
from .models import TaskDependency, TaskStatus, TaskWithDependencies, TaskWithPriority
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
        self.task_repository = TaskRepository(db_path=db_path)
        logger.debug(f"TaskDependencyRepository initialized with database: {db_path}")

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
                self.task_repository.get_task(ids).status in ([TaskStatus.CANCELLED.value, TaskStatus.COMPLETED.value])  # type: ignore
                for ids in [task_id, blocker_id]
            ):  # type: ignore fail fast
                raise DependencyError("task is closed")
        except AttributeError as exc:
            raise TaskNotFoundError(task_id) from exc

        if self._cycle_check(task_id, blocker_id):
            raise DependencyError("Dependency causes a cycle")

        dependency = TaskDependency(task_id=task_id, blocker_id=blocker_id)
        with get_connection(self.db_path) as conn:
            conn.execute(
                INSERT_DEPENDENCY,
                (
                    str(dependency.dependency_id),
                    str(dependency.task_id),
                    str(dependency.blocker_id),
                    dependency.created_at.isoformat(),
                ),
            )
            conn.commit()
            logger.info(f"Created dependency: task-{dependency.task_id}, blocker-{dependency.blocker_id}")
        return dependency

    def remove_dependency(self, task_id: UUID, blocker_id: UUID) -> None:
        """Remove a dependency between two tasks.

        Args:
            task_id: UUID of the blocked task.
            blocker_id: UUID of the blocker task.

        Raises:
            DependencyError: If dependency does not exist.
        """
        logger.debug(f"Removing dependency: task-{task_id}, blocker-{blocker_id}")
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(DELETE_DEPENDENCY, (str(task_id), str(blocker_id)))
            if not cursor.rowcount:
                logger.error(f"Cannot remove dependency: not found (task-{task_id}, blocker-{blocker_id})")
                raise DependencyError(f"Dependency not found: blocker-{blocker_id} -> task-{task_id}")
            conn.commit()
            logger.info(f"Removed dependency: task-{task_id}, blocker-{blocker_id}")

    def get_blockers(self, task_id: UUID) -> list[Task]:
        """Get all active tasks blocking this task.

        Args:
            task_id: UUID of the blocked task.

        Returns:
            List of Task objects that are blocking (status: pending/in_progress).
        """
        logger.debug(f"Retrieving active blockers for task: {task_id}")
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(SELECT_ACTIVE_BLOCKERS, (str(task_id),))
            rows = cursor.fetchall()

        blockers = [task for row in rows if (task := self.task_repository.get_task(task_id=UUID(row["blocker_id"])))]
        logger.debug(f"Found {len(blockers)} active blocker(s) for task {task_id}")
        return blockers

    def get_blocked(self, blocker_id: UUID) -> list[Task]:
        """Get all tasks blocked by this task.

        Args:
            blocker_id: UUID of the blocker task.

        Returns:
            List of Task objects that are blocked by this task.
        """
        logger.debug(f"Retrieving tasks blocked by: {blocker_id}")
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(SELECT_BLOCKED_TASKS, (str(blocker_id),))
            rows = cursor.fetchall()

        blocked = [task for row in rows if (task := self.task_repository.get_task(task_id=UUID(row["task_id"])))]
        logger.debug(f"Found {len(blocked)} blocked task(s) by {blocker_id}")
        return blocked

    def _cycle_check(self, task_id: UUID, blocker_id: UUID) -> bool:
        """Detect circular dependencies using BFS.

        Checks if blocker_id transitively depends on task_id.
        If true, adding "task_id blocked by blocker_id" would create a cycle.

        Args:
            task_id: Task that would be blocked.
            blocker_id: Task that would block.

        Returns:
            True if adding dependency would create a cycle.
        """
        logger.debug(f"Checking for circular dependency: task-{task_id}, blocker-{blocker_id}")
        visited: set[UUID] = set()
        queue: deque[UUID] = deque([blocker_id])

        while queue:
            current = queue.popleft()
            if current == task_id:
                logger.warning(f"Circular dependency detected: task-{task_id} -> blocker-{blocker_id}")
                return True
            if current in visited:
                continue
            visited.add(current)
            # Follow the blocking chain upward: who blocks current?
            queue.extend(blocker.task_id for blocker in self.get_blockers(current))

        logger.debug(f"No circular dependency found for task-{task_id}, blocker-{blocker_id}")
        return False

    def calculate_effective_priorities(self, tasks: list[TaskWithDependencies] | None = None) -> dict[UUID, float]:
        """Calculate effective priorities for all tasks in batch.

        Priority flows upstream: if a high-priority task is blocked by a low-priority task,
        the blocker inherits the higher priority.

        Formula: effective_priority = max(intrinsic_priority, max(downstream_priorities))

        This method calculates all priorities in a single pass, avoiding redundant calculations.

        Args:
            tasks: Optional list of tasks to calculate priorities for. If None, uses all tasks.

        Returns:
            Dict mapping task_id to effective_priority.

        Example:
            >>> priorities = repo.calculate_effective_priorities()
            >>> print(f"Task A: {priorities[task_a_id]:.3f}")
            0.90
        """
        task_repo = TaskRepository(self.db_path)
        # Import here to avoid circular dependency
        if tasks is None:
            tasks = task_repo.list_tasks_with_deps()

        memo: dict[UUID, float] = {}

        def _calculate_recursive(task_id: UUID) -> float:
            """Recursive helper with memoization."""
            # Already calculated
            if task_id in memo:
                return memo[task_id]

            # Get intrinsic priority
            task = task_repo.get_task(task_id)
            if not task:
                logger.warning(f"Task not found during priority calculation: {task_id}")
                memo[task_id] = 0.0
                return 0.0

            intrinsic = task.priority

            # Get tasks this blocks (downstream)
            blocked_tasks = self.get_blocked(task_id)

            if not blocked_tasks:
                # Leaf node - no downstream tasks to inherit from
                memo[task_id] = intrinsic
                return intrinsic

            # Recursively calculate downstream priorities
            downstream_priorities = [_calculate_recursive(blocked.task_id) for blocked in blocked_tasks]

            # Inherit max downstream priority
            effective = max(intrinsic, *downstream_priorities)
            memo[task_id] = effective

            logger.debug(f"Task {task_id} effective priority: {effective:.3f} (intrinsic: {intrinsic:.3f})")
            return effective

        # Calculate for all tasks
        for task in tasks:
            if task.task_id not in memo:
                _calculate_recursive(task.task_id)

        return memo

    def list_tasks_with_priority(self, status: TaskStatus | None = None) -> list[TaskWithPriority]:
        """List tasks with dependency counts and effective priorities.

        Combines data from tasks_full view with calculated effective priorities.

        Args:
            status: Optional status filter.

        Returns:
            List of TaskWithPriority models with all enriched data.

        Example:
            >>> tasks = repo.list_tasks_with_priority(TaskStatus.PENDING)
            >>> for task in sorted(tasks, key=lambda t: t.effective_priority, reverse=True):
            ...     print(f"{task.title}: {task.effective_priority:.3f}")
        """
        # Get tasks with dependency counts
        tasks_with_deps = self.task_repository.list_tasks_with_deps()

        # Filter by status if provided
        if status:
            tasks_with_deps = [t for t in tasks_with_deps if t.status == status]

        # Calculate effective priorities for all tasks
        priorities = self.calculate_effective_priorities(
            [TaskWithDependencies(**t.model_dump()) for t in tasks_with_deps]
        )

        # Build TaskWithPriority models
        return [
            TaskWithPriority(**task.model_dump(), effective_priority=priorities[task.task_id])
            for task in tasks_with_deps
        ]
