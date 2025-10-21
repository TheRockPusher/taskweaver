"""Task repository for CRUD operations."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from loguru import logger

from .connection import DEFAULT_DB_PATH, get_connection
from .exceptions import TaskNotFoundError
from .models import Task, TaskCreate, TaskStatus, TaskUpdate, TaskWithDependencies
from .schema import (
    DELETE_TASK,
    INSERT_TASK,
    SELECT_ALL_TASKS,
    SELECT_ALL_TASKS_DEPENDENCY,
    SELECT_TASK_BY_ID,
    UPDATE_TASK,
)


class TaskRepository:
    """Repository for task CRUD operations.

    Designed for AI agent tool usage with clear, single-purpose methods.
    """

    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        """Initialize repository.

        Args:
            db_path: Path to SQLite database file.

        """
        self.db_path = db_path
        logger.debug(f"TaskRepository initialized with database: {db_path}")

    def create_task(self, task_data: TaskCreate) -> Task:
        """Create a new task.

        Args:
            task_data: Task creation data.

        Returns:
            Created task with generated ID and timestamps.

        """
        logger.debug(f"Creating task: title='{task_data.title}'")
        task = Task(
            title=task_data.title,
            description=task_data.description,
        )

        with get_connection(self.db_path) as conn:
            conn.execute(
                INSERT_TASK,
                (
                    str(task.task_id),
                    task.title,
                    task.description,
                    task.status.value,
                    task.created_at.isoformat(),
                    task.updated_at.isoformat(),
                ),
            )
            conn.commit()
            logger.info(f"Created task {task.task_id}: '{task.title}' [status={task.status.value}]")

        return task

    def get_task(self, task_id: UUID) -> Task | None:
        """Get task by ID.

        Args:
            task_id: Task UUID.

        Returns:
            Task if found, None otherwise.

        """
        logger.debug(f"Retrieving task: {task_id}")
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(SELECT_TASK_BY_ID, (str(task_id),))
            row = cursor.fetchone()

        if row is None:
            logger.debug(f"Task not found: {task_id}")
            return None

        logger.debug(f"Task found: {task_id} - '{row['title']}'")
        return Task(
            task_id=UUID(row["task_id"]),
            title=row["title"],
            description=row["description"],
            status=TaskStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def list_tasks(self, status: TaskStatus | None = None) -> list[Task]:
        """List tasks, optionally filtered by status.

        Args:
            status: Optional status filter. If None, returns all tasks.

        Returns:
            List of tasks ordered by created_at desc.

        """
        filter_msg = f"status={status.value}" if status else "no filter"
        logger.debug(f"Listing tasks ({filter_msg})")

        with get_connection(self.db_path) as conn:
            if status is None:
                cursor = conn.execute(SELECT_ALL_TASKS)
            else:
                # Filter by status
                query = "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC"
                cursor = conn.execute(query, (status.value,))

            rows = cursor.fetchall()

        task_count = len(rows)
        logger.info(f"Retrieved {task_count} task(s) ({filter_msg})")

        return [
            Task(
                task_id=UUID(row["task_id"]),
                title=row["title"],
                description=row["description"],
                status=TaskStatus(row["status"]),
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
            for row in rows
        ]

    def list_tasks_with_deps(self) -> list[TaskWithDependencies]:
        """List all tasks with a count of blockers and blocked.

        Returns:
            list[TaskWithDependencies]: _description_
        """
        logger.debug("Listing dependency tasks")

        with get_connection(self.db_path) as conn:
            cursor = conn.execute(SELECT_ALL_TASKS_DEPENDENCY)

            rows = cursor.fetchall()

        task_count = len(rows)
        logger.info(f"Retrieved {task_count} task(s)")

        return [
            TaskWithDependencies(
                task_id=UUID(row["task_id"]),
                title=row["title"],
                description=row["description"],
                status=TaskStatus(row["status"]),
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                tasks_blocked_count=row["tasks_blocked_count"],
                active_blocker_count=row["active_blocker_count"],
            )
            for row in rows
        ]

    def update_task(self, task_id: UUID, task_data: TaskUpdate) -> Task:
        """Update a task.

        Args:
            task_id: Task UUID.
            task_data: Fields to update.

        Returns:
            Updated task.

        Raises:
            TaskNotFoundError: If task does not exist.

        """
        logger.debug(f"Updating task: {task_id}")
        # Get existing task
        task = self.get_task(task_id)
        if task is None:
            logger.error(f"Cannot update task {task_id}: not found")
            raise TaskNotFoundError(task_id)

        # Track changes for logging
        changes = []
        # Update fields
        if task_data.title is not None:
            changes.append(f"title: '{task.title}' -> '{task_data.title}'")
            task.title = task_data.title
        if task_data.description is not None:
            changes.append("description updated")
            task.description = task_data.description
        if task_data.status is not None:
            old_status = task.status
            new_status = task_data.status
            changes.append(f"status: {old_status} -> {new_status}")
            task.status = task_data.status

        task.updated_at = datetime.now(UTC)

        with get_connection(self.db_path) as conn:
            # Extract status value (handle both TaskStatus enum and string)
            status_value = task.status
            conn.execute(
                UPDATE_TASK,
                (
                    task.title,
                    task.description,
                    status_value,
                    task.updated_at.isoformat(),
                    str(task_id),
                ),
            )
            conn.commit()
            logger.info(f"Updated task {task_id}: {', '.join(changes)}")

        return task

    def mark_completed(self, task_id: UUID) -> Task:
        """Mark a task as completed.

        Args:
            task_id: Task UUID.

        Returns:
            Updated task.

        Raises:
            TaskNotFoundError: If task does not exist.

        """
        logger.debug(f"Marking task as completed: {task_id}")
        return self.update_task(task_id, TaskUpdate(status=TaskStatus.COMPLETED))

    def mark_in_progress(self, task_id: UUID) -> Task:
        """Mark a task as in progress.

        Args:
            task_id: Task UUID.

        Returns:
            Updated task.

        Raises:
            TaskNotFoundError: If task does not exist.

        """
        logger.debug(f"Marking task as in progress: {task_id}")
        return self.update_task(task_id, TaskUpdate(status=TaskStatus.IN_PROGRESS))

    def mark_cancelled(self, task_id: UUID) -> Task:
        """Mark a task as cancelled.

        Args:
            task_id: Task UUID.

        Returns:
            Updated task.

        Raises:
            TaskNotFoundError: If task does not exist.

        """
        logger.debug(f"Marking task as cancelled: {task_id}")
        return self.update_task(task_id, TaskUpdate(status=TaskStatus.CANCELLED))

    def delete_task(self, task_id: UUID) -> None:
        """Delete a task.

        Args:
            task_id: Task UUID.

        Raises:
            TaskNotFoundError: If task does not exist.

        """
        logger.debug(f"Deleting task: {task_id}")
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(DELETE_TASK, (str(task_id),))
            conn.commit()
            deleted = cursor.rowcount > 0

        if deleted:
            logger.info(f"Deleted task {task_id}")
        else:
            logger.error(f"Cannot delete task {task_id}: not found")
            raise TaskNotFoundError(task_id)
