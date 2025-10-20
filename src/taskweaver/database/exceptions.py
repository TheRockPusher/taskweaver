"""Custom exceptions for database operations."""

from uuid import UUID


class TaskNotFoundError(Exception):
    """Raised when a task cannot be found in the database.

    Attributes:
        task_id: The UUID of the task that was not found.

    """

    def __init__(self, task_id: UUID) -> None:
        """Initialize the exception.

        Args:
            task_id: The UUID of the task that was not found.

        """
        self.task_id = task_id
        super().__init__(f"Task not found: {task_id}")


class DependencyError(Exception):
    """Raised when dependency operation fails."""

    def __init__(self, message: str, task_id: str | None = None) -> None:
        """Initialize the exception.

        Args:
            message: Error message describing the failure.
            task_id: Optional task UUID related to the error.
        """
        self.task_id = task_id
        super().__init__(message)
