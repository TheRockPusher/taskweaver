"""Completion repository for CRUD operations."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from loguru import logger

from .connection import get_connection, get_database_path
from .exceptions import CompletionNotFoundError, TaskNotFoundError
from .models import Completion, CompletionCreate, CompletionStatus, Task, TaskStatus
from .priority_service import completion_priority_factors, refresh_priorities
from .schema import (
    DELETE_COMPLETION,
    INSERT_COMPLETION,
    SELECT_ALL_COMPLETIONS,
    SELECT_COMPLETION_BY_ID,
    SELECT_COMPLETION_BY_TASK_ID,
    SELECT_COMPLETIONS_BY_STATUS,
)


class CompletionRepository:
    """Repository for completion CRUD operations.

    Manages completion records for pattern learning and variance analysis.
    Each completion is an immutable snapshot of a task's completion event.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize repository.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = db_path if db_path is not None else get_database_path()
        logger.debug(f"CompletionRepository initialized with database: {db_path}")

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Completion:
        data = dict(row)
        if data["priority_factors"] is not None:
            data["priority_factors"] = json.loads(data["priority_factors"])
        return Completion.model_validate(data)

    @staticmethod
    def _insert(conn: sqlite3.Connection, completion: Completion) -> None:
        conn.execute(
            INSERT_COMPLETION,
            (
                str(completion.completion_id),
                str(completion.task_id),
                completion.status.value,
                completion.closed_at.isoformat(),
                completion.duration_expected,
                completion.duration_actual,
                completion.conclusion,
                completion.created_at.isoformat(),
                completion.raw_duration_min,
                completion.category,
                json.dumps(completion.priority_factors) if completion.priority_factors is not None else None,
            ),
        )

    def create_completion(self, completion_data: CompletionCreate) -> Completion:
        """Record a historical event without changing task status.

        Raw duration and category default to the task's immutable baseline and
        current category. Explicit snapshots support historical imports. Learning
        and active scores refresh in the same transaction. For atomic task closure
        and dependency cleanup, use complete_task.
        """
        with get_connection(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (str(completion_data.task_id),)).fetchone()
            if row is None:
                raise TaskNotFoundError(completion_data.task_id)
            task = Task.model_validate(dict(row))
            data = completion_data.model_dump()
            if data["raw_duration_min"] is None:
                data["raw_duration_min"] = task.raw_duration_min
            if data["category"] is None:
                data["category"] = task.category
            if data["priority_factors"] is None:
                data["priority_factors"] = completion_priority_factors(conn, task.task_id)
            completion = Completion.model_validate(data)
            self._insert(conn, completion)
            refresh_priorities(conn)
            conn.commit()
        return completion

    def complete_task(
        self,
        task_id: UUID,
        actual_minutes: int,
        conclusion: str | None = None,
        status: CompletionStatus = CompletionStatus.COMPLETED,
    ) -> Completion:
        """Atomically record a task's closure and remove all its dependency edges.

        An exact retry returns the original immutable event. Different duration,
        conclusion, or status raises ValueError rather than rewriting evidence.
        A previously closed task without a record can be recorded in the same
        status, but its closure cannot be silently reversed.
        """
        status = CompletionStatus(status)
        with get_connection(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (str(task_id),)).fetchone()
            if row is None:
                raise TaskNotFoundError(task_id)
            task = Task.model_validate(dict(row))
            if task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED) and task.status.value != status.value:
                raise ValueError(f"Task already closed with a different status: {task_id}")
            previous = conn.execute(SELECT_COMPLETION_BY_TASK_ID, (str(task_id),)).fetchone()
            if previous is not None:
                completion = self._from_row(previous)
                if (
                    completion.duration_actual != actual_minutes
                    or completion.conclusion != conclusion
                    or completion.status != status
                ):
                    raise ValueError(f"Conflicting completion already recorded for task: {task_id}")
            else:
                completion = Completion(
                    task_id=task_id,
                    status=status,
                    duration_expected=task.duration_min,
                    duration_actual=actual_minutes,
                    raw_duration_min=task.raw_duration_min,
                    category=task.category,
                    conclusion=conclusion,
                    priority_factors=completion_priority_factors(conn, task_id),
                )
                self._insert(conn, completion)
            closed = conn.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ? AND status != ?",
                (status.value, datetime.now(UTC).isoformat(), str(task_id), status.value),
            )
            cleaned = conn.execute(
                "DELETE FROM task_dependencies WHERE task_id = ? OR blocker_id = ?", (str(task_id), str(task_id))
            )
            if previous is None or closed.rowcount or cleaned.rowcount:
                refresh_priorities(conn)
            conn.commit()
        return completion

    def get_completion(self, completion_id: UUID) -> Completion | None:
        """Get completion by ID.

        Args:
            completion_id: Completion UUID.

        Returns:
            Completion if found, None otherwise.
        """
        logger.debug(f"Retrieving completion: {completion_id}")
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(SELECT_COMPLETION_BY_ID, (str(completion_id),))
            row = cursor.fetchone()

        if row is None:
            logger.debug(f"Completion not found: {completion_id}")
            return None

        logger.debug(f"Completion found: {completion_id}")
        return self._from_row(row)

    def get_completion_by_task_id(self, task_id: UUID) -> Completion | None:
        """Get completion by task ID.

        Args:
            task_id: Task UUID.

        Returns:
            Completion if found, None otherwise.
        """
        logger.debug(f"Retrieving completion for task: {task_id}")
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(SELECT_COMPLETION_BY_TASK_ID, (str(task_id),))
            row = cursor.fetchone()

        if row is None:
            logger.debug(f"No completion found for task: {task_id}")
            return None

        logger.debug(f"Completion found for task: {task_id}")
        return self._from_row(row)

    def list_completions(self, status: CompletionStatus | None = None) -> list[Completion]:
        """List completions, optionally filtered by status.

        Args:
            status: Optional status filter. If None, returns all completions.

        Returns:
            List of completions ordered by closed_at desc.
        """
        filter_msg = f"status={status.value}" if status else "no filter"
        logger.debug(f"Listing completions ({filter_msg})")

        with get_connection(self.db_path) as conn:
            if status is None:
                cursor = conn.execute(SELECT_ALL_COMPLETIONS)
            else:
                cursor = conn.execute(SELECT_COMPLETIONS_BY_STATUS, (status.value,))

            rows = cursor.fetchall()

        completion_count = len(rows)
        logger.info(f"Retrieved {completion_count} completion(s) ({filter_msg})")

        return [self._from_row(row) for row in rows]

    def delete_completion(self, completion_id: UUID) -> None:
        """Delete a completion record and atomically refresh learning and active scores.

        Args:
            completion_id: Completion UUID.

        Raises:
            CompletionNotFoundError: If completion does not exist.
        """
        logger.debug(f"Deleting completion: {completion_id}")
        with get_connection(self.db_path) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            if not conn.execute(DELETE_COMPLETION, (str(completion_id),)).rowcount:
                raise CompletionNotFoundError(completion_id)
            refresh_priorities(conn)
        logger.info(f"Deleted completion {completion_id}")
