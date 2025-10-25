"""Completion repository for CRUD operations."""

from datetime import datetime
from pathlib import Path
from uuid import UUID

from loguru import logger

from .connection import DEFAULT_DB_PATH, get_connection
from .exceptions import CompletionNotFoundError
from .models import Completion, CompletionCreate, CompletionStatus
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

    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        """Initialize repository.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = db_path
        logger.debug(f"CompletionRepository initialized with database: {db_path}")

    def create_completion(self, completion_data: CompletionCreate) -> Completion:
        """Create a new completion record.

        Args:
            completion_data: Completion creation data.

        Returns:
            Created completion with generated ID and timestamps.
        """
        logger.debug(f"Creating completion: task_id={completion_data.task_id}, status={completion_data.status}")
        completion = Completion(
            task_id=completion_data.task_id,
            status=completion_data.status,
            closed_at=completion_data.closed_at,
            duration_expected=completion_data.duration_expected,
            duration_actual=completion_data.duration_actual,
            conclusion=completion_data.conclusion,
        )

        with get_connection(self.db_path) as conn:
            conn.execute(
                INSERT_COMPLETION,
                (
                    str(completion.completion_id),
                    str(completion.task_id),
                    completion.status,
                    completion.closed_at.isoformat(),
                    completion.duration_expected,
                    completion.duration_actual,
                    completion.conclusion,
                    completion.created_at.isoformat(),
                ),
            )
            conn.commit()
            logger.info(
                f"Created completion {completion.completion_id}: task={completion.task_id} "
                f"[status={completion.status}, variance={completion.variance_minutes}min]"
            )

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
        return Completion(
            completion_id=UUID(row["completion_id"]),
            task_id=UUID(row["task_id"]),
            status=CompletionStatus(row["status"]),
            closed_at=datetime.fromisoformat(row["closed_at"]),
            duration_expected=row["duration_expected"],
            duration_actual=row["duration_actual"],
            conclusion=row["conclusion"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

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
        return Completion(
            completion_id=UUID(row["completion_id"]),
            task_id=UUID(row["task_id"]),
            status=CompletionStatus(row["status"]),
            closed_at=datetime.fromisoformat(row["closed_at"]),
            duration_expected=row["duration_expected"],
            duration_actual=row["duration_actual"],
            conclusion=row["conclusion"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

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

        return [
            Completion(
                completion_id=UUID(row["completion_id"]),
                task_id=UUID(row["task_id"]),
                status=CompletionStatus(row["status"]),
                closed_at=datetime.fromisoformat(row["closed_at"]),
                duration_expected=row["duration_expected"],
                duration_actual=row["duration_actual"],
                conclusion=row["conclusion"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    def delete_completion(self, completion_id: UUID) -> None:
        """Delete a completion record.

        Args:
            completion_id: Completion UUID.

        Raises:
            CompletionNotFoundError: If completion does not exist.
        """
        logger.debug(f"Deleting completion: {completion_id}")
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(DELETE_COMPLETION, (str(completion_id),))
            conn.commit()
            deleted = cursor.rowcount > 0

        if deleted:
            logger.info(f"Deleted completion {completion_id}")
        else:
            logger.error(f"Cannot delete completion {completion_id}: not found")
            raise CompletionNotFoundError(completion_id)
