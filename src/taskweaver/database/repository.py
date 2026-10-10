"""Task persistence with atomic status cleanup and fresh MCDA rankings."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from .connection import get_connection, get_database_path
from .exceptions import TaskNotFoundError
from .models import Task, TaskCreate, TaskStatus, TaskUpdate, TaskWithDependencies
from .planning import estimate_duration
from .priority_service import refresh_priorities
from .schema import (
    DELETE_TASK,
    INSERT_TASK,
    SELECT_ALL_TASKS,
    SELECT_ALL_TASKS_DEPENDENCY,
    SELECT_TASK_BY_ID,
    UPDATE_TASK,
)

_NULLABLE_FIELDS = frozenset(
    {
        "description",
        "goal_id",
        "skill_domain",
        "required_skill_level",
        "priority_score",
        "priority_updated_at",
    }
)
_TERMINAL_STATUSES = (TaskStatus.COMPLETED, TaskStatus.CANCELLED)


def _require_task(conn: sqlite3.Connection, task_id: UUID) -> Task:
    row = conn.execute(SELECT_TASK_BY_ID, (str(task_id),)).fetchone()
    if row is None:
        raise TaskNotFoundError(task_id)
    return Task.model_validate(dict(row))


def _validate_goal(conn: sqlite3.Connection, goal_id: UUID | None) -> None:
    if goal_id is not None and not conn.execute("SELECT 1 FROM goals WHERE goal_id = ?", (str(goal_id),)).fetchone():
        msg = f"Goal not found: {goal_id}"
        raise ValueError(msg)


def _create_task(conn: sqlite3.Connection, task_data: TaskCreate) -> Task:
    task = Task.model_validate(task_data.model_dump(exclude_none=True))
    _validate_goal(conn, task.goal_id)
    task.duration_min = estimate_duration(conn, task.category, task.raw_duration_min).adjusted_minutes
    conn.execute(INSERT_TASK, task.model_dump(mode="json"))
    refresh_priorities(conn)
    return _require_task(conn, task.task_id)


def _update_task(conn: sqlite3.Connection, task_id: UUID, task_data: TaskUpdate) -> Task:
    changes = {
        key: value
        for key, value in task_data.model_dump(exclude_unset=True).items()
        if value is not None or key in _NULLABLE_FIELDS
    }
    task = _require_task(conn, task_id)
    task = Task.model_validate(task.model_dump() | changes | {"updated_at": datetime.now(UTC)})
    _validate_goal(conn, task.goal_id)
    conn.execute(UPDATE_TASK, task.model_dump(mode="json"))
    if task.status in _TERMINAL_STATUSES:
        conn.execute("DELETE FROM task_dependencies WHERE blocker_id = ?", (str(task_id),))
    refresh_priorities(conn)
    return _require_task(conn, task_id)


class TaskRepository:
    """Persist tasks and their derived rankings in the same SQLite transaction."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path if db_path is not None else get_database_path()

    def create_task(self, task_data: TaskCreate, *, connection: sqlite3.Connection | None = None) -> Task:
        """Create a task, adjusting its original duration estimate exactly once.

        Args:
            task_data: Validated task fields and optional original duration baseline.
            connection: An active caller-owned transaction, or None to commit independently.

        Returns:
            Persisted task with current MCDA score and learned duration estimate.
        """
        if connection is not None:
            if not connection.in_transaction:
                msg = "A supplied connection must have an active transaction"
                raise ValueError(msg)
            return _create_task(connection, task_data)
        with get_connection(self.db_path) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            return _create_task(conn, task_data)

    def get_task(self, task_id: UUID) -> Task | None:
        """Retrieve a task, returning None when it does not exist."""
        with get_connection(self.db_path) as conn:
            row = conn.execute(SELECT_TASK_BY_ID, (str(task_id),)).fetchone()
        return Task.model_validate(dict(row)) if row is not None else None

    def list_tasks(self, status: TaskStatus | None = None) -> list[Task]:
        """List tasks newest first, optionally filtering by status."""
        with get_connection(self.db_path) as conn:
            rows = (
                conn.execute(SELECT_ALL_TASKS).fetchall()
                if status is None
                else conn.execute(
                    "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC", (status.value,)
                ).fetchall()
            )
        return [Task.model_validate(dict(row)) for row in rows]

    def list_tasks_with_deps(self) -> list[TaskWithDependencies]:
        """List active tasks with active blocker and downstream counts."""
        with get_connection(self.db_path) as conn:
            rows = conn.execute(SELECT_ALL_TASKS_DEPENDENCY).fetchall()
        return [TaskWithDependencies.model_validate(dict(row)) for row in rows]

    def update_task(
        self, task_id: UUID, task_data: TaskUpdate, *, connection: sqlite3.Connection | None = None
    ) -> Task:
        """Apply supplied fields, clearing nullable fields when explicitly set to None.

        The original raw_duration_min remains immutable. Editing duration_min changes
        the working estimate without reapplying learning. Completing or cancelling a
        blocker permanently deletes its outgoing edges in this same transaction.
        MCDA fields are derived again for active tasks, including explicit overrides.

        Args:
            task_id: Task to update.
            task_data: Fields explicitly supplied by the caller.
            connection: An active caller-owned transaction, or None to commit independently.

        Returns:
            Persisted task with refreshed rankings.

        Raises:
            TaskNotFoundError: If the task does not exist.
        """
        if connection is not None:
            if not connection.in_transaction:
                msg = "A supplied connection must have an active transaction"
                raise ValueError(msg)
            return _update_task(connection, task_id, task_data)
        with get_connection(self.db_path) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            return _update_task(conn, task_id, task_data)

    def update_task_scores(
        self, task_id: UUID, urgency: int | None = None, importance: int | None = None, effort: int | None = None
    ) -> Task:
        """Update supplied 1..5 scores and refresh every affected active ranking."""
        return self.update_task(task_id, TaskUpdate(urgency=urgency, importance=importance, effort=effort))

    def list_tasks_by_priority(self, status: TaskStatus | None = None, limit: int | None = None) -> list[Task]:
        """List current intrinsic MCDA scores descending with deterministic ties.

        Args:
            status: Optional task status filter.
            limit: Maximum number of results, or None for all matching tasks.

        Returns:
            Ranked tasks, with tasks lacking a score last.

        Raises:
            ValueError: If limit is negative.
        """
        if limit is not None and limit < 0:
            msg = "limit must be nonnegative"
            raise ValueError(msg)
        status_value = status.value if status is not None else None
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """SELECT * FROM tasks WHERE (? IS NULL OR status = ?)
                ORDER BY priority_score DESC, created_at DESC, task_id LIMIT ?""",
                (status_value, status_value, -1 if limit is None else limit),
            ).fetchall()
        return [Task.model_validate(dict(row)) for row in rows]

    def mark_completed(self, task_id: UUID) -> Task:
        """Complete a task and immediately release tasks it blocks."""
        return self.update_task(task_id, TaskUpdate(status=TaskStatus.COMPLETED))

    def mark_in_progress(self, task_id: UUID) -> Task:
        """Set a task's status to in progress."""
        return self.update_task(task_id, TaskUpdate(status=TaskStatus.IN_PROGRESS))

    def mark_cancelled(self, task_id: UUID) -> Task:
        """Cancel a task and immediately release tasks it blocks."""
        return self.update_task(task_id, TaskUpdate(status=TaskStatus.CANCELLED))

    def delete_task(self, task_id: UUID) -> None:
        """Delete a task, cascading its edges, completions, and priority history.

        Raises:
            TaskNotFoundError: If the task does not exist.
        """
        with get_connection(self.db_path) as conn, conn:
            if not conn.execute(DELETE_TASK, (str(task_id),)).rowcount:
                raise TaskNotFoundError(task_id)
            refresh_priorities(conn)
