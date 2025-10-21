"""Database models using Pydantic."""

from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class TaskStatus(str, Enum):
    """Task status enumeration."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Task(BaseModel):
    """Task model - mirrors database schema exactly.

    - Entity-specific primary key (task_id)
    - Models mirror database exactly (no field mapping)

    """

    task_id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(
        use_enum_values=True,  # Store enum values, not names
    )


class TaskCreate(BaseModel):
    """Model for creating new tasks."""

    title: str = Field(min_length=1, max_length=500)
    description: str | None = None


class TaskUpdate(BaseModel):
    """Model for updating tasks - all fields optional."""

    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    status: TaskStatus | None = None
    model_config = ConfigDict(
        use_enum_values=True,  # Store enum values, not names
    )


class TaskDependency(BaseModel):
    """Model Storing the dependency between 2 tasks."""

    dependency_id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    blocker_id: UUID
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TaskWithDependencies(Task):
    """Task enriched with dependency counts from tasks_full view.

    Extends base Task model with aggregated dependency metrics:
    - tasks_blocked_count: Number of tasks blocked by this task
    - active_blocker_count: Number of active tasks blocking this task

    Use this model when querying the tasks_full view or when you need
    dependency counts without separate database queries.

    Example:
        >>> task = TaskWithDependencies(
        ...     title="Implement feature X",
        ...     tasks_blocked_count=3,  # Blocks 3 other tasks
        ...     active_blocker_count=1,  # 1 task blocking this
        ... )
    """

    tasks_blocked_count: int = Field(default=0, ge=0, description="Number of tasks blocked by this task")
    active_blocker_count: int = Field(
        default=0, ge=0, description="Number of active tasks (pending/in_progress) blocking this task"
    )

    model_config = ConfigDict(
        use_enum_values=True,  # Store enum values, not names
        from_attributes=True,  # Enable ORM mode for SQLite Row objects
    )

    @property
    def is_blocked(self) -> bool:
        """Check if this task has any active blockers."""
        return self.active_blocker_count > 0

    @property
    def is_blocking_others(self) -> bool:
        """Check if this task is blocking other tasks."""
        return self.tasks_blocked_count > 0
