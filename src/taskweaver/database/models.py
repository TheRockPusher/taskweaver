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
    duration_min: int = Field(ge=1)
    llm_value: float = Field(ge=0, le=10)
    requirement: str = Field(min_length=1, max_length=500)

    model_config = ConfigDict(
        use_enum_values=True,  # Store enum values, not names
    )

    @property
    def priority(self) -> float:
        """Calculate priority score as value per minute (llm_value / duration_min).

        Higher priority = higher value delivered per minute of effort.

        Returns:
            Priority score (higher is better). Ranges from ~0.004 (value=1, duration=240min)
            to 10.0 (value=10, duration=1min).

        Example:
            >>> task = Task(title="Quick win", duration_min=30, llm_value=9.0, requirement="Done")
            >>> task.priority
            0.3  # High value, short duration = good priority
            >>> task2 = Task(title="Long grind", duration_min=240, llm_value=3.0, requirement="Done")
            >>> task2.priority
            0.0125  # Low value, long duration = poor priority
        """
        return self.llm_value / self.duration_min


class TaskCreate(BaseModel):
    """Model for creating new tasks."""

    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    duration_min: int = Field(ge=1)
    llm_value: float = Field(ge=0, le=10)
    requirement: str = Field(min_length=1, max_length=500)


class TaskUpdate(BaseModel):
    """Model for updating tasks - all fields optional."""

    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    status: TaskStatus | None = None
    duration_min: int | None = Field(default=None, ge=1)
    llm_value: float | None = Field(default=None, ge=0, le=10)
    requirement: str | None = Field(default=None, min_length=1, max_length=500)

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

    @property
    def is_blocked(self) -> bool:
        """Check if this task has any active blockers."""
        return self.active_blocker_count > 0

    @property
    def is_blocking_others(self) -> bool:
        """Check if this task is blocking other tasks."""
        return self.tasks_blocked_count > 0


class TaskWithPriority(TaskWithDependencies):
    """Task enriched with dependency counts AND effective priority.

    Extends TaskWithDependencies with calculated effective priority from DAG.

    Example:
        >>> task = TaskWithPriority(
        ...     title="Setup CI/CD",
        ...     duration_min=120,
        ...     llm_value=3.0,
        ...     requirement="Setup pipeline",
        ...     tasks_blocked_count=1,
        ...     active_blocker_count=0,
        ...     effective_priority=0.90
        ... )
        >>> task.priority  # intrinsic
        0.025
        >>> task.effective_priority  # inherited from downstream
        0.90
    """

    effective_priority: float = Field(description="Effective priority considering DAG inheritance")
