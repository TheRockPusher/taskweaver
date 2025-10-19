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
        populate_by_name=True,
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
